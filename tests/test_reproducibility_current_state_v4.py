import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v4.json"


class ReproducibilityCurrentStateV4Tests(unittest.TestCase):
    def test_current_navigation_hashes_counts_and_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v6.json")
        sec = data["current_sec_iapd_gate"]
        self.assertEqual(
            (sec["planned"], sec["resolved"], sec["available"], sec["unavailable"], sec["unresolved"]),
            (115, 107, 52, 55, 8),
        )
        self.assertEqual(sec["next_release"], "V6")
        self.assertEqual(sec["minimum_delay_seconds"], 60.0)
        self.assertEqual(sec["authoritative_executor"], "scripts.retry_sec_edgar_iapd_wayback_availability_v6_1")
        self.assertFalse(sec["capture_plan_allowed"])

        sufficiency = data["data_sufficiency"]
        self.assertEqual(sufficiency["verified_existing_raw_files"], 278)
        self.assertEqual(sufficiency["historical_train_rows"], 3916)
        self.assertEqual(sufficiency["fresh_validated_groups"], 0)
        self.assertEqual(sufficiency["fresh_required_groups"], 300)

        self.assertEqual(data["post_availability_tooling"]["capture_plan_version"], "v3")
        self.assertEqual(data["post_availability_tooling"]["capture_release_version"], "v3")
        for gate in (
            "network_execution_allowed_now",
            "candidate_domain_access_allowed",
            "capture_allowed",
            "validation_or_test_opening_allowed",
            "training_allowed",
            "model_scoring_allowed",
        ):
            self.assertFalse(data["decision"][gate])

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/reproducibility-current-state-v4.md", readme)
        self.assertIn("V1–V3", readme)


if __name__ == "__main__":
    unittest.main()
