import unittest

from app.services.credentials import CredentialCipher
from app.integrations.base import NotificationResult, Notifier
from app.services.alerting import HealthAlertManager


class RecordingNotifier(Notifier):
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, title: str, body: str, recipient: str | None = None) -> NotificationResult:
        self.messages.append((title, body))
        return NotificationResult("TEST", True)

    def health_check(self) -> bool:
        return True


class CredentialTest(unittest.TestCase):
    def test_encrypt_round_trip_does_not_store_plaintext(self) -> None:
        cipher = CredentialCipher("test-encryption-key")
        ciphertext, nonce = cipher.encrypt({"api_key": "secret-value"})
        self.assertNotIn("secret-value", ciphertext)
        self.assertEqual(cipher.decrypt(ciphertext, nonce)["api_key"], "secret-value")


class AlertingTest(unittest.TestCase):
    def test_health_alerts_are_deduplicated_and_recovery_is_announced(self) -> None:
        manager = HealthAlertManager()
        notifier = RecordingNotifier()
        failed = [{"provider": "openai", "probe": "FAIL"}]
        passing = [{"provider": "openai", "probe": "PASS"}]
        self.assertEqual(manager.process(failed, notifier), ["openai:FAIL"])
        self.assertEqual(manager.process(failed, notifier), [])
        self.assertEqual(manager.process(passing, notifier), ["openai:PASS"])
        self.assertEqual(len(notifier.messages), 2)


if __name__ == "__main__":
    unittest.main()
