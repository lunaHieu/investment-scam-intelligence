import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "analyses" / "project_state_gap_ledger_v26.json"


class ProjectStateGapLedgerV26Tests(unittest.TestCase):
    def test_c2_and_c3_preflight_state(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.assertEqual(data["analysis_id"], "ISI_PROJECT_STATE_GAP_LEDGER_V26")
        for section in ("inputs", "implementation"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        c2 = data["state_amendments"]["P3_C2_EXTERNAL_ARTIFACT_INTAKE_PREFLIGHT"]
        self.assertEqual(c2["source_contracts"], 4)
        self.assertEqual(c2["completed_submissions"], 0)
        self.assertTrue(data["decision"]["c2_preflight_complete"])
        self.assertFalse(data["decision"]["c2_intake_complete"])
        self.assertTrue(data["decision"]["c3_preflight_complete"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
