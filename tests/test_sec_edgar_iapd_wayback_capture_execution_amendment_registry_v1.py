import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_execution_amendment_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdWaybackCaptureExecutionAmendmentRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_decoupled_crash_safe_capture_contract(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertEqual(findings["capture_plan_rows"], 58)
        self.assertEqual(
            findings["capture_plan_by_cohort"],
            {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12},
        )
        self.assertFalse(findings["availability_v10_is_capture_prerequisite"])
        self.assertFalse(findings["same_process_after_availability_429_allowed"])
        self.assertTrue(findings["reservation_before_first_request"])
        self.assertTrue(findings["checkpoint_after_each_row"])
        self.assertFalse(findings["automatic_partial_resume_allowed"])

        decision = data["decision"]
        self.assertTrue(decision["capture_execution_allowed_now"])
        self.assertFalse(decision["candidate_live_domain_access_allowed"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
