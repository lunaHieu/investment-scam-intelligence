import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "registry" / "analyses" / "text_model_choice_dossier_v5.json"


class TextModelChoiceDossierV5Tests(unittest.TestCase):
    def test_evidence_hashes_and_no_model_gate_opened(self) -> None:
        data = json.loads(DOSSIER.read_text(encoding="utf-8"))
        for item in data["inputs"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        evidence = data["verified_evidence"]
        self.assertLess(evidence["e5_challenger_pooled_macro_f1"], evidence["linear_reference_pooled_macro_f1"])
        self.assertEqual(evidence["target_text_training_eligible_records"], 0)
        self.assertEqual(evidence["verified_vietnamese_supply"], 0)
        self.assertEqual(data["model_family_decisions"]["ai_agent"], "WORKFLOW_QA_AND_EVIDENCE_PACKET_ASSISTANT_ONLY")
        self.assertFalse(data["decision"]["current_reference_deployable"])
        self.assertFalse(data["decision"]["new_model_configuration_authorized"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
