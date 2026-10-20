import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_wayback_capture_plan_release_v5.json"


class SecEdgarIapdWaybackCapturePlanReleaseRegistryV5Tests(unittest.TestCase):
    def test_registry_pins_exact_partial_resolved_release(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        findings = data["findings"]
        self.assertEqual(findings["source_candidate_count"], 115)
        self.assertEqual(findings["planned_capture_count"], 58)
        self.assertEqual(findings["planned_by_cohort"], {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12})
        self.assertEqual(findings["quarantined_unresolved_count"], 2)
        self.assertEqual(
            findings["quarantined_plan_ids"],
            ["SEC_IAPD_20261007_HOLDOUT_011", "SEC_IAPD_20261007_HOLDOUT_018"],
        )
        self.assertEqual(findings["not_before"], "2026-10-21T14:19:54.213531+07:00")
        self.assertTrue(data["decision"]["capture_allowed_at_or_after_not_before"])
        self.assertFalse(data["decision"]["capture_allowed_now"])
        self.assertFalse(data["decision"]["labeling_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
