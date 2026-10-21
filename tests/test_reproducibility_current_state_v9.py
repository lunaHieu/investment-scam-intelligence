import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v9.json"


class ReproducibilityCurrentStateV9Tests(unittest.TestCase):
    def test_current_guide_points_to_ledger_v11_and_v10(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v11.json")
        gate = data["current_sec_iapd_gate"]
        self.assertEqual(gate["v10_retry_rows"], 2)
        self.assertEqual(gate["capture_plan_rows"], 58)
        self.assertTrue(gate["capture_release_v5_preserved"])
        self.assertFalse(gate["capture_executed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
