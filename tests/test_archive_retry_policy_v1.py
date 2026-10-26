import unittest
from datetime import datetime

from scripts.archive_retry_policy_v1 import decide


NOW = "2026-10-26T09:00:00+07:00"


class ArchiveRetryPolicyV1Tests(unittest.TestCase):
    def test_local_finalization_is_offline_and_immediate(self) -> None:
        result = decide(failure_class="LOCAL_FINALIZATION", observed_at=NOW, network_attempts=1, raw_bytes_persisted=True, response_metadata_persisted=True)
        self.assertEqual(result["action"], "OFFLINE_RECONCILE_NOW")
        self.assertFalse(result["project_blocked"])
        self.assertIsNone(result["not_before"])

    def test_retry_after_overrides_local_backoff(self) -> None:
        result = decide(failure_class="HTTP_429", observed_at=NOW, network_attempts=1, retry_after="120")
        self.assertEqual(result["not_before"], "2026-10-26T09:02:00+07:00")
        self.assertEqual(result["action"], "RETRY_AFTER_RATE_LIMIT")

    def test_rate_limit_without_header_uses_bounded_exponential_backoff(self) -> None:
        first = decide(failure_class="HTTP_429", observed_at=NOW, network_attempts=1, consecutive_failures=1)
        fourth = decide(failure_class="HTTP_429", observed_at=NOW, network_attempts=1, consecutive_failures=4)
        self.assertEqual(datetime.fromisoformat(first["not_before"]).hour, 9)
        self.assertEqual(datetime.fromisoformat(first["not_before"]).minute, 15)
        self.assertEqual(datetime.fromisoformat(fourth["not_before"]).day, 27)

    def test_retry_budget_is_finite(self) -> None:
        result = decide(failure_class="TIMEOUT", observed_at=NOW, network_attempts=3)
        self.assertEqual(result["action"], "QUARANTINE_RETRY_BUDGET_EXHAUSTED")
        self.assertFalse(result["same_request_allowed"])

    def test_identical_parser_failure_is_not_retried(self) -> None:
        result = decide(failure_class="PARSER_LIMITATION", observed_at=NOW, network_attempts=1)
        self.assertEqual(result["action"], "NO_IDENTICAL_RETRY_QUARANTINE")
        self.assertFalse(result["project_blocked"])


if __name__ == "__main__":
    unittest.main()
