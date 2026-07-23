from __future__ import annotations

from uuid import uuid4

from app.integrations.base import AIProvider, Notifier, NotificationResult, PublishResult, Publisher


class MockAIProvider(AIProvider):
    name = "MOCK_AI"

    def generate_social_copies(self, topic: str, channels: list[str]) -> dict[str, str]:
        return {channel.lower(): f"Draft copy for {topic} ({channel.lower()})." for channel in channels}

    def health_check(self) -> bool:
        return True


class MockPublisher(Publisher):
    name = "MOCK_NUELINK"

    def publish(self, channel: str, topic: str, copy: str, live_url: str | None) -> PublishResult:
        if channel.upper() in {"YOUTUBE", "REDDIT"}:
            return PublishResult(self.name, channel, None, None, manual_required=True)
        post_id = f"mock_{uuid4().hex[:12]}"
        return PublishResult(self.name, channel, post_id, f"https://mock.nuelink.local/{post_id}")

    def health_check(self) -> bool:
        return True


class MockNotifier(Notifier):
    name = "MOCK_SLACK"

    def send(self, title: str, body: str, recipient: str | None = None) -> NotificationResult:
        return NotificationResult(self.name, True)


class MockEmailNotifier(Notifier):
    name = "EMAIL"

    def send(self, title: str, body: str, recipient: str | None = None) -> NotificationResult:
        return NotificationResult(self.name, bool(recipient), f"mock-email-{recipient}" if recipient else None)

    def health_check(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True
