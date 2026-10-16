import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v3.json"


class ReproducibilityCurrentStateV3Tests(unittest.TestCase):
    def test_guide_is_hash_bound_to_current_closed_gate_state(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                item["sha256"],
                item["path"],
            )

        self.assertTrue(all(data["coverage"].values()))
        self.assertEqual(
            data["current_entrypoint"],
            "registry/analyses/project_state_gap_ledger_v5.json",
        )
        sec = data["current_sec_iapd_gate"]
        self.assertEqual(sec["planned"], 115)
        self.assertEqual(sec["resolved"], 92)
        self.assertEqual(sec["unresolved"], 23)
        self.assertEqual(sec["next_release"], "V5")
        self.assertEqual(
            sec["not_before"], "2026-10-17T01:19:27.607186+07:00"
        )
        self.assertFalse(sec["capture_plan_allowed"])

        decision = data["decision"]
        self.assertTrue(decision["guide_v3_is_authoritative_navigation_entry"])
        for gate in (
            "network_execution_allowed_now",
            "candidate_domain_access_allowed",
            "capture_allowed",
            "validation_or_test_opening_allowed",
            "training_allowed",
            "model_scoring_allowed",
        ):
            self.assertFalse(decision[gate])


if __name__ == "__main__":
    unittest.main()
