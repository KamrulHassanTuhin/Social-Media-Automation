import unittest

from app.domain.status import InvalidStatusTransition, PublishingReadiness, assert_transition
from app.services.generation import validate_generated_output
from app.services.idempotency import publishing_idempotency_key


class WorkflowRulesTest(unittest.TestCase):
    def test_valid_and_invalid_transitions(self) -> None:
        assert_transition("NEEDS_REVIEW", "APPROVED")
        with self.assertRaises(InvalidStatusTransition):
            assert_transition("NOT_STARTED", "APPROVED")

    def test_readiness_exposes_missing_gates(self) -> None:
        readiness = PublishingReadiness(True, True, False, True, False, True)
        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.missing(), ["publisher", "media"])

    def test_generation_output_requires_all_channels(self) -> None:
        result = validate_generated_output({"linkedin": "Only one channel"})
        self.assertFalse(result.valid)
        self.assertTrue(any("Missing channels" in error for error in result.errors))

    def test_idempotency_key_is_stable(self) -> None:
        first = publishing_idempotency_key("w", "c", "LINKEDIN", 1, None)
        second = publishing_idempotency_key("w", "c", "LINKEDIN", 1, None)
        self.assertEqual(first, second)
        self.assertNotEqual(first, publishing_idempotency_key("w", "c", "GBP", 1, None))


if __name__ == "__main__":
    unittest.main()
