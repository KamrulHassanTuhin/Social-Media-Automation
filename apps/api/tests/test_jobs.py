import asyncio
import tempfile
import unittest

from app.jobs.outbox import InMemoryNotificationOutbox
from app.jobs.publishing import InMemoryPublishingStore
from app.jobs.queue import InMemoryJobQueue
from app.jobs.worker import JobWorker
from app.integrations.base import IntegrationError, PublishResult
from app.integrations.factory import IntegrationBundle
from app.integrations.mock import MockAIProvider, MockEmailNotifier, MockNotifier, MockPublisher
from app.repositories.content import InMemoryContentRepository
from app.services.media import LocalMediaStore, MediaValidationError
from app.services.idempotency import publishing_idempotency_key
from app.services.rate_limit import ProviderRateLimiter, RateLimitExceeded


class JobAndMediaTest(unittest.TestCase):
    def test_queue_is_idempotent_and_retries(self) -> None:
        queue = InMemoryJobQueue()
        first = queue.enqueue("TEST", "ws_demo", {}, "same-key")
        second = queue.enqueue("TEST", "ws_demo", {}, "same-key")
        self.assertEqual(first.id, second.id)
        claimed = queue.claim_next()
        self.assertIsNotNone(claimed)
        assert claimed is not None
        queue.fail(claimed, "temporary")
        self.assertEqual(claimed.status, "RETRY_SCHEDULED")

    def test_provider_rate_limiter_blocks_after_limit(self) -> None:
        limiter = ProviderRateLimiter(1)
        limiter.acquire("openai")
        with self.assertRaises(RateLimitExceeded):
            limiter.acquire("openai")

    def test_generation_worker_creates_copy_versions_and_sends_outbox(self) -> None:
        repository = InMemoryContentRepository()
        queue = InMemoryJobQueue()
        outbox = InMemoryNotificationOutbox()
        worker = JobWorker(queue, outbox, repository)
        queue.enqueue("GENERATE_SOCIAL_COPY", "ws_demo", {"content_id": "cnt_demo_01", "channels": ["LINKEDIN"], "actor_id": "user_demo"}, "generation:test")
        completed = worker.drain_local()
        self.assertEqual([job.status for job in completed], ["SUCCEEDED", "SUCCEEDED"])
        self.assertEqual(repository.get("ws_demo", "cnt_demo_01").automation_status, "NEEDS_REVIEW")
        self.assertEqual(len(repository.list_copy_versions("cnt_demo_01")), 1)
        self.assertEqual(next(iter(outbox._events.values())).status, "SENT")

    def test_email_outbox_delivery_is_retryable_and_tracked(self) -> None:
        repository = InMemoryContentRepository()
        queue = InMemoryJobQueue()
        outbox = InMemoryNotificationOutbox()
        publishing = InMemoryPublishingStore()
        worker = JobWorker(queue, outbox, repository, publishing, IntegrationBundle(MockAIProvider(), MockPublisher(), MockNotifier(), MockEmailNotifier()))
        event = outbox.enqueue("ws_demo", "EMAIL", {"to": "member@axis.local", "subject": "Welcome", "body": "Join us"}, "email:test")
        queue.enqueue("SEND_NOTIFICATION", "ws_demo", {"event_id": event.id}, "notification:test")
        worker.drain_local()
        self.assertEqual(outbox.get(event.id).status, "SENT")

    def test_publishing_worker_confirms_mock_provider(self) -> None:
        repository = InMemoryContentRepository()
        queue = InMemoryJobQueue()
        outbox = InMemoryNotificationOutbox()
        publishing = InMemoryPublishingStore()
        worker = JobWorker(queue, outbox, repository, publishing)
        record = publishing.enqueue("ws_demo", "cnt_demo_01", "linkedin", publishing_idempotency_key("ws_demo", "cnt_demo_01", "linkedin", 1, None))
        queue.enqueue("PUBLISH_CHANNEL", "ws_demo", {"content_id": "cnt_demo_01", "channel": "linkedin", "publishing_job_id": record.id}, "publish:test")
        completed = worker.drain_local()
        self.assertEqual(completed[0].status, "SUCCEEDED")
        self.assertEqual(publishing.for_content("cnt_demo_01")[0].status, "SUCCEEDED")

    def test_partial_publish_does_not_hide_failed_channel(self) -> None:
        class OneChannelFails(MockPublisher):
            def publish(self, channel: str, topic: str, copy: str, live_url: str | None) -> PublishResult:
                if channel.lower() == "facebook_instagram":
                    raise IntegrationError("simulated provider failure")
                return super().publish(channel, topic, copy, live_url)

        repository = InMemoryContentRepository()
        item = repository.get("ws_demo", "cnt_demo_01")
        assert item is not None
        item.copies["facebook_instagram"] = "A second channel copy"
        queue = InMemoryJobQueue()
        outbox = InMemoryNotificationOutbox()
        publishing = InMemoryPublishingStore()
        worker = JobWorker(queue, outbox, repository, publishing, IntegrationBundle(MockAIProvider(), OneChannelFails(), MockNotifier()))
        for channel in ("linkedin", "facebook_instagram"):
            record = publishing.enqueue("ws_demo", item.id, channel, f"partial:{channel}")
            queue.enqueue("PUBLISH_CHANNEL", "ws_demo", {"content_id": item.id, "channel": channel, "publishing_job_id": record.id, "actor_id": "user_demo"}, f"publish:{channel}")
        worker.drain_local()
        self.assertEqual(repository.get("ws_demo", item.id).automation_status, "PARTIALLY_PUBLISHED")
        statuses = {job.channel: job.status for job in publishing.for_content(item.id)}
        self.assertEqual(statuses["linkedin"], "SUCCEEDED")
        self.assertEqual(statuses["facebook_instagram"], "FAILED")

    def test_media_store_rejects_unsupported_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalMediaStore(directory)
            with self.assertRaises(MediaValidationError):
                asyncio.run(store.save("ws_demo", "project_axis", None, "file.exe", "application/octet-stream", b"data"))

    def test_media_store_checks_file_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalMediaStore(directory)
            with self.assertRaises(MediaValidationError):
                asyncio.run(store.save("ws_demo", "project_axis", None, "file.png", "image/png", b"not-a-png"))


if __name__ == "__main__":
    unittest.main()
