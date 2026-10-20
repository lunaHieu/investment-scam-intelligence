import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v8.json"


class ReproducibilityCurrentStateV8Tests(unittest.TestCase):
    def test_current_navigation_hashes_counts_and_capture_gate(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v10.json")
        sec = data["current_sec_iapd_gate"]
        self.assertEqual(
            (sec["planned"], sec["resolved"], sec["available"], sec["unavailable"], sec["unresolved"]),
            (115, 113, 58, 55, 2),
        )
        self.assertEqual(sec["capture_plan_rows"], 58)
        self.assertEqual(sec["capture_release_version"], "V5")
        self.assertEqual(sec["capture_not_before"], "2026-10-21T14:19:54.213531+07:00")
        self.assertFalse(sec["capture_allowed_now"])

        self.assertFalse(data["decision"]["candidate_domain_access_allowed"])
        self.assertTrue(data["decision"]["capture_allowed_at_or_after_not_before"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
