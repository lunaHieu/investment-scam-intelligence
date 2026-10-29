import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSESSMENT = ROOT / "configs" / "target_text_corpus_v1_sanitized_text_source_assessment_v1.json"


class SanitizedTextSourceAssessmentV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.value = json.loads(ASSESSMENT.read_text(encoding="utf-8"))

    def test_inputs_are_hash_bound(self) -> None:
        for item in self.value["inputs"]:
            payload = (ROOT / item["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"])

    def test_evidence_sources_are_not_silently_promoted_to_model_text(self) -> None:
        self.assertEqual(self.value["findings"]["sources_assessed"], 3)
        self.assertEqual(self.value["findings"]["sources_ready_for_fresh_model_text"], 0)
        self.assertEqual(self.value["findings"]["new_training_rows_authorized"], 0)
        self.assertTrue(all(row["observed_artifact_text_records"] == 0 for row in self.value["source_assessments"]))

    def test_all_execution_and_model_gates_remain_closed(self) -> None:
        decision = self.value["decision"]
        self.assertTrue(decision["new_sanitized_text_source_discovery_required"])
        for key in ("dfpi_ubcknn_fca_acquisition_release_may_be_prepared", "network_execution_allowed", "candidate_live_domain_access_allowed", "labeling_allowed", "training_allowed"):
            self.assertFalse(decision[key])


if __name__ == "__main__":
    unittest.main()
