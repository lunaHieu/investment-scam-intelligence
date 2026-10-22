import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v11.json"


class ReproducibilityCurrentStateV11Tests(unittest.TestCase):
    def test_current_guide_points_to_ledger_v13_and_v10_result(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v13.json")
        state = data["current_sec_iapd_state"]
        self.assertEqual(state["availability_resolved"], 113)
        self.assertEqual(state["availability_unresolved"], 2)
        self.assertTrue(state["v10_stopped_on_http_429"])
        self.assertEqual(state["owner_accepted_labels"], 42)
        self.assertEqual(data["data_sufficiency"]["fresh_v1_core_admitted_groups"], 0)
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["model_scoring_allowed"])


if __name__ == "__main__":
    unittest.main()
