from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import get_settings
from app.integrations.base import AIProvider, Notifier, Publisher
from app.integrations.http import EmailNotifier, NuelinkPublisher, OpenAIChatProvider, SlackWebhookNotifier
from app.integrations.mock import MockAIProvider, MockEmailNotifier, MockNotifier, MockPublisher


@dataclass(frozen=True)
class IntegrationBundle:
    ai: AIProvider
    publisher: Publisher
    notifier: Notifier
    email: Notifier | None = None


def build_integrations() -> IntegrationBundle:
    settings = get_settings()
    if settings.app_env == "local":
        return IntegrationBundle(MockAIProvider(), MockPublisher(), MockNotifier(), MockEmailNotifier())

    # Keep the control plane available when optional provider credentials have
    # not been added yet. Health endpoints expose the missing configuration,
    # while the mock adapters keep review, scheduling, and demo workflows usable.
    return IntegrationBundle(
        OpenAIChatProvider(settings.openai_api_key, settings.openai_model, settings.openai_base_url) if settings.openai_api_key else MockAIProvider(),
        NuelinkPublisher(settings.nuelink_api_key, settings.nuelink_base_url, settings.nuelink_destination_id) if settings.nuelink_api_key else MockPublisher(),
        SlackWebhookNotifier(settings.slack_webhook_url) if settings.slack_webhook_url else MockNotifier(),
        EmailNotifier(settings.email_api_key, settings.email_base_url, settings.email_from) if settings.email_api_key else MockEmailNotifier(),
    )
