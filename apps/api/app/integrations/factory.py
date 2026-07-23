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
    if not settings.openai_api_key or not settings.nuelink_api_key or not settings.slack_webhook_url:
        raise RuntimeError("OPENAI_API_KEY, NUELINK_API_KEY, and SLACK_WEBHOOK_URL are required outside local mode.")
    return IntegrationBundle(
        OpenAIChatProvider(settings.openai_api_key, settings.openai_model, settings.openai_base_url),
        NuelinkPublisher(settings.nuelink_api_key, settings.nuelink_base_url, settings.nuelink_destination_id),
        SlackWebhookNotifier(settings.slack_webhook_url),
        EmailNotifier(settings.email_api_key, settings.email_base_url, settings.email_from) if settings.email_api_key else None,
    )
