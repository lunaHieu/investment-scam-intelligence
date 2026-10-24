import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_v11_supplemental_capture_plan_release_v1.json"


class SecEdgarIapdV11SupplementalCaptureRegistryTests(unittest.TestCase):
    def test_registry_pins_two_row_plan_release_and_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        findings = data["findings"]
        self.assertEqual(findings["source_candidate_count"], 115)
        self.assertEqual(findings["planned_capture_count"], 2)
        self.assertEqual(findings["ordered_plan_ids"], ["TTCV1_EDGAR_AVAIL_HOLDOUT_011", "TTCV1_EDGAR_AVAIL_HOLDOUT_018"])
        self.assertFalse(findings["original_capture_plan_mutated"])
        self.assertTrue(data["decision"]["capture_plan_qa_passed"])
        self.assertFalse(data["decision"]["capture_allowed_now"])
        self.assertFalse(data["decision"]["text_extraction_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
