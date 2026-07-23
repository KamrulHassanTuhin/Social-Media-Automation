from __future__ import annotations

from dataclasses import dataclass


class IntegrationError(RuntimeError):
    """Provider failure that can be retried or shown in the Error Center."""


@dataclass(frozen=True)
class PublishResult:
    provider: str
    channel: str
    external_post_id: str | None
    external_post_url: str | None
    manual_required: bool = False


@dataclass(frozen=True)
class NotificationResult:
    provider: str
    delivered: bool
    provider_message_id: str | None = None


class AIProvider:
    name = "UNKNOWN"

    def generate_social_copies(self, topic: str, channels: list[str]) -> dict[str, str]:
        raise NotImplementedError

    def health_check(self) -> bool:
        return False


class Publisher:
    name = "UNKNOWN"

    def publish(self, channel: str, topic: str, copy: str, live_url: str | None) -> PublishResult:
        raise NotImplementedError

    def health_check(self) -> bool:
        return False


class Notifier:
    name = "UNKNOWN"

    def send(self, title: str, body: str, recipient: str | None = None) -> NotificationResult:
        raise NotImplementedError

    def health_check(self) -> bool:
        return False
