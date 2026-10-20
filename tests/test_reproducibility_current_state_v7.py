import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v7.json"


class ReproducibilityCurrentStateV7Tests(unittest.TestCase):
    def test_current_navigation_hashes_counts_and_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v9.json")
        sec = data["current_sec_iapd_gate"]
        self.assertEqual(
            (sec["planned"], sec["resolved"], sec["available"], sec["unavailable"], sec["unresolved"]),
            (115, 113, 58, 55, 2),
        )
        self.assertEqual(sec["next_release"], "V9")
        self.assertEqual(sec["authoritative_executor"], "scripts.retry_sec_edgar_iapd_wayback_availability_v9")
        self.assertFalse(sec["capture_plan_allowed"])

        tooling = data["post_availability_tooling"]
        self.assertIsNone(tooling["capture_plan_version"])
        self.assertIsNone(tooling["capture_release_version"])
        self.assertFalse(tooling["supports_availability_v9"])
        self.assertFalse(tooling["v4_fallback_allowed"])

        for gate in (
            "network_execution_allowed_now",
            "candidate_domain_access_allowed",
            "capture_allowed",
            "validation_or_test_opening_allowed",
            "training_allowed",
            "model_scoring_allowed",
        ):
            self.assertFalse(data["decision"][gate])


if __name__ == "__main__":
    unittest.main()
