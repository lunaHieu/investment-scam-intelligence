import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v25.json"


class ProjectStateGapLedgerV25Tests(unittest.TestCase):
    def test_c3_preflight_state_and_hashes(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.assertEqual(data["analysis_id"], "ISI_PROJECT_STATE_GAP_LEDGER_V25")
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        state = data["state_amendments"]["P3_C3_LANGUAGE_RESPONSE_PREFLIGHT"]
        self.assertEqual(state["template_records"], 42)
        self.assertEqual(state["human_decisions_materialized"], 0)
        self.assertTrue(data["decision"]["c3_preflight_complete"])
        self.assertFalse(data["decision"]["c3_human_response_complete"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
