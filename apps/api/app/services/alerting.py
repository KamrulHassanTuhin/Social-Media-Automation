from __future__ import annotations

from typing import Any

from app.integrations.base import Notifier


class HealthAlertManager:
    """Emit one alert per provider state transition to avoid notification storms."""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}

    def process(self, checks: list[dict[str, Any]], notifier: Notifier) -> list[str]:
        emitted: list[str] = []
        for check in checks:
            provider = str(check["provider"])
            state = str(check.get("probe") or "UNKNOWN")
            previous = self._states.get(provider)
            self._states[provider] = state
            try:
                if state == "FAIL" and previous != "FAIL":
                    notifier.send(
                        f"Nova provider alert: {provider}",
                        f"{provider} health probe failed. Check the Operations screen and provider credentials.",
                    )
                    emitted.append(f"{provider}:FAIL")
                elif state == "PASS" and previous == "FAIL":
                    notifier.send(
                        f"Nova provider recovered: {provider}",
                        f"{provider} health probe is passing again.",
                    )
                    emitted.append(f"{provider}:PASS")
            except Exception:
                # Health probes must remain observable even if the alert channel is down.
                continue
        return emitted


health_alert_manager = HealthAlertManager()
