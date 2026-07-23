from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from app.integrations.base import AIProvider, IntegrationError, Notifier, NotificationResult, PublishResult, Publisher


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - URL is operator-configured, never user-provided
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - normalize provider errors at the adapter boundary
        raise IntegrationError(str(exc)) from exc


class OpenAIChatProvider(AIProvider):
    name = "OPENAI"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate_social_copies(self, topic: str, channels: list[str]) -> dict[str, str]:
        channel_keys = [channel.lower() for channel in channels]
        payload = {
            "model": self.model,
            "temperature": 0.6,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Return only JSON. Generate concise channel-specific social copy."},
                {"role": "user", "content": json.dumps({"topic": topic, "channels": channel_keys})},
            ],
        }
        result = _post_json(f"{self.base_url}/chat/completions", {"Authorization": f"Bearer {self.api_key}"}, payload)
        try:
            content = result["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {key: str(parsed[key]) for key in channel_keys}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise IntegrationError("OpenAI returned an invalid social copy payload.") from exc

    def health_check(self) -> bool:
        request = Request(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}, method="GET")
        try:
            with urlopen(request, timeout=10):  # noqa: S310 - operator-configured provider URL
                return True
        except Exception:
            return False


class SlackWebhookNotifier(Notifier):
    name = "SLACK"

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, title: str, body: str, recipient: str | None = None) -> NotificationResult:
        _post_json(self.webhook_url, {}, {"text": f"*{title}*\n{body}"})
        return NotificationResult(self.name, True)

    def health_check(self) -> bool:
        return bool(self.webhook_url)


class EmailNotifier(Notifier):
    name = "EMAIL"

    def __init__(self, api_key: str, base_url: str, sender: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.sender = sender

    def send(self, title: str, body: str, recipient: str | None = None) -> NotificationResult:
        if not recipient:
            raise IntegrationError("Email notification is missing a recipient.")
        result = _post_json(f"{self.base_url}/emails", {"Authorization": f"Bearer {self.api_key}"}, {"from": self.sender, "to": [recipient], "subject": title, "text": body})
        return NotificationResult(self.name, True, result.get("id"))

    def health_check(self) -> bool:
        return bool(self.api_key and self.sender)


class NuelinkPublisher(Publisher):
    """Minimal adapter boundary; destination mapping is intentionally workspace-specific."""

    name = "NUELINK"

    def __init__(self, api_key: str, base_url: str, destination_id: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.destination_id = destination_id

    def publish(self, channel: str, topic: str, copy: str, live_url: str | None) -> PublishResult:
        result = _post_json(f"{self.base_url}/posts", {"Authorization": f"Bearer {self.api_key}"}, {"channel": channel, "destination_id": self.destination_id, "title": topic, "text": copy, "url": live_url})
        return PublishResult(self.name, channel, result.get("id"), result.get("url"))

    def health_check(self) -> bool:
        request = Request(self.base_url, headers={"Authorization": f"Bearer {self.api_key}"}, method="GET")
        try:
            with urlopen(request, timeout=10):  # noqa: S310 - operator-configured provider URL
                return True
        except Exception:
            return False
