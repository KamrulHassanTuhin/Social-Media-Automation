from __future__ import annotations

from dataclasses import dataclass


class InvalidStatusTransition(ValueError):
    """Raised when an action tries to skip a guarded workflow state."""


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "NOT_STARTED": {"QUEUED"},
    "QUEUED": {"GENERATING", "FAILED", "CANCELED"},
    "GENERATING": {"NEEDS_REVIEW", "FAILED", "CANCELED"},
    "NEEDS_REVIEW": {"APPROVED", "CHANGES_REQUESTED", "CANCELED"},
    "CHANGES_REQUESTED": {"NEEDS_REVIEW", "CANCELED"},
    "APPROVED": {"READY_TO_PUBLISH", "NEEDS_REVIEW"},
    "READY_TO_PUBLISH": {"PUBLISHING", "CANCELED"},
    "PUBLISHING": {"PUBLISHED", "PARTIALLY_PUBLISHED", "FAILED", "CANCELED"},
    "PARTIALLY_PUBLISHED": {"PUBLISHING", "PUBLISHED", "FAILED"},
    "FAILED": {"QUEUED", "CANCELED"},
    "PUBLISHED": set(),
    "CANCELED": set(),
}


def assert_transition(current: str, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransition(f"Cannot transition automation status from {current} to {target}.")


@dataclass(frozen=True)
class PublishingReadiness:
    approved: bool
    has_live_url: bool
    has_publisher: bool
    has_required_copy: bool
    has_media: bool
    integration_connected: bool

    @property
    def ready(self) -> bool:
        return all((
            self.approved,
            self.has_live_url,
            self.has_publisher,
            self.has_required_copy,
            self.has_media,
            self.integration_connected,
        ))

    def missing(self) -> list[str]:
        checks = {
            "approval": self.approved,
            "live_url": self.has_live_url,
            "publisher": self.has_publisher,
            "required_copy": self.has_required_copy,
            "media": self.has_media,
            "integration": self.integration_connected,
        }
        return [name for name, passed in checks.items() if not passed]
