from __future__ import annotations

from app.jobs.outbox import InMemoryNotificationOutbox
from app.jobs.publishing import InMemoryPublishingStore
from app.jobs.queue import InMemoryJobQueue, Job
from app.integrations.factory import IntegrationBundle, build_integrations
from app.repositories.content import ContentRecord
from app.services.rate_limit import ProviderRateLimiter


class JobWorker:
    def __init__(self, queue: InMemoryJobQueue, outbox: InMemoryNotificationOutbox, content_repository, publishing_store: InMemoryPublishingStore | None = None, integrations: IntegrationBundle | None = None, rate_limiter: ProviderRateLimiter | None = None) -> None:
        self.queue = queue
        self.outbox = outbox
        self.content_repository = content_repository
        self.publishing_store = publishing_store
        self.integrations = integrations or build_integrations()
        self.rate_limiter = rate_limiter or ProviderRateLimiter()

    def run_once(self) -> Job | None:
        job = self.queue.claim_next()
        if not job:
            return None
        try:
            if job.job_type == "GENERATE_SOCIAL_COPY":
                self._generate_social_copy(job)
            elif job.job_type == "SEND_NOTIFICATION":
                self._send_notification(job)
            elif job.job_type == "PUBLISH_CHANNEL":
                self._publish_channel(job)
            else:
                raise ValueError(f"Unsupported job type: {job.job_type}")
            return self.queue.complete(job)
        except Exception as exc:  # noqa: BLE001 - worker must persist retry state
            if job.job_type == "PUBLISH_CHANNEL" and self.publishing_store:
                self.publishing_store.mark_failed(job.payload.get("publishing_job_id", ""), str(exc))
                self._reconcile_content(job.workspace_id, job.payload.get("content_id", ""), job.payload.get("actor_id", "system"))
            return self.queue.fail(job, str(exc))

    def drain_local(self, maximum: int = 10) -> list[Job]:
        completed: list[Job] = []
        for _ in range(maximum):
            job = self.run_once()
            if not job:
                break
            completed.append(job)
        return completed

    def _generate_social_copy(self, job: Job) -> None:
        payload = job.payload
        item: ContentRecord | None = self.content_repository.get(job.workspace_id, payload["content_id"])
        if not item:
            raise ValueError("Content item was not found.")
        item.automation_status = "GENERATING"
        self.content_repository.update(item, payload["actor_id"])
        self.rate_limiter.acquire(f"{job.workspace_id}:ai")
        item.copies = self.integrations.ai.generate_social_copies(item.topic, payload["channels"])
        for channel, body in item.copies.items():
            self.content_repository.save_copy_version(item.id, channel, body, payload["actor_id"])
        item.automation_status = "NEEDS_REVIEW"
        self.content_repository.update(item, payload["actor_id"])
        event = self.outbox.enqueue(job.workspace_id, "COPY_READY", {"content_id": item.id, "topic": item.topic}, f"copy-ready:{item.id}:{item.updated_at.isoformat()}", payload["actor_id"])
        self.queue.enqueue("SEND_NOTIFICATION", job.workspace_id, {"event_id": event.id}, f"notification:{event.id}")

    def _send_notification(self, job: Job) -> None:
        event_id = job.payload["event_id"]
        event = self.outbox.get(event_id)
        if not event:
            raise ValueError("Notification event was not found.")
        self.rate_limiter.acquire(f"{job.workspace_id}:notifications")
        notifier = self.integrations.email if event.event_type == "EMAIL" else self.integrations.notifier
        if not notifier:
            raise ValueError("Email provider is not configured.")
        recipient = event.payload.get("to")
        if event.event_type == "EMAIL" and recipient and self.outbox.is_suppressed(job.workspace_id, str(recipient)):
            self.outbox.mark_canceled(event, "Recipient is suppressed after a prior bounce or unsubscribe.")
            return
        result = notifier.send(event.payload.get("subject", event.event_type), event.payload.get("body", str(event.payload)), recipient)
        if not result.delivered:
            raise ValueError("Notification provider did not confirm delivery.")
        self.outbox.mark_sent(event, result.provider_message_id)

    def _publish_channel(self, job: Job) -> None:
        if not self.publishing_store:
            raise ValueError("Publishing store is not configured.")
        payload = job.payload
        item: ContentRecord | None = self.content_repository.get(job.workspace_id, payload["content_id"])
        if not item:
            raise ValueError("Content item was not found.")
        publishing_job = next((candidate for candidate in self.publishing_store.for_content(item.id) if candidate.id == payload["publishing_job_id"]), None)
        if not publishing_job:
            raise ValueError("Publishing job record was not found.")
        publishing_job.status = "PROCESSING"
        self.rate_limiter.acquire(f"{job.workspace_id}:publishing")
        body = item.copies.get(payload["channel"].lower(), "")
        result = self.integrations.publisher.publish(payload["channel"], item.topic, body, item.live_url)
        publishing_job.external_post_id = result.external_post_id
        publishing_job.external_post_url = result.external_post_url
        publishing_job.status = "MANUAL_REQUIRED" if result.manual_required else "SUCCEEDED"
        self._reconcile_content(job.workspace_id, item.id, payload.get("actor_id", "system"))

    def _reconcile_content(self, workspace_id: str, content_id: str, actor_id: str) -> None:
        if not self.publishing_store or not content_id:
            return
        jobs = self.publishing_store.for_content(content_id)
        item = self.content_repository.get(workspace_id, content_id)
        if not item or not jobs:
            return
        statuses = {job.status for job in jobs}
        if statuses == {"SUCCEEDED"}:
            target = "PUBLISHED"
        elif "FAILED" in statuses and ("SUCCEEDED" in statuses or "MANUAL_REQUIRED" in statuses):
            target = "PARTIALLY_PUBLISHED"
        elif "FAILED" in statuses and statuses.issubset({"FAILED"}):
            target = "FAILED"
        elif "MANUAL_REQUIRED" in statuses and statuses.issubset({"SUCCEEDED", "MANUAL_REQUIRED"}):
            target = "PARTIALLY_PUBLISHED"
        else:
            target = "PUBLISHING"
        if item.automation_status != target:
            item.automation_status = target
            self.content_repository.update(item, actor_id)
