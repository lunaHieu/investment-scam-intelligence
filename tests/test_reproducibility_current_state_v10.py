import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v10.json"


class ReproducibilityCurrentStateV10Tests(unittest.TestCase):
    def test_current_guide_points_to_ledger_v12_and_owner_acceptance(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v12.json")
        state = data["current_sec_iapd_state"]
        self.assertEqual(state["captured"], 57)
        self.assertEqual(state["reviewable"], 56)
        self.assertEqual(state["owner_accepted_labels"], 42)
        self.assertEqual(state["uncertain_retained"], 14)
        self.assertEqual(data["data_sufficiency"]["fresh_v1_core_admitted_groups"], 0)
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["model_scoring_allowed"])


if __name__ == "__main__":
    unittest.main()
