import hashlib
import unittest

from scripts.verify_external_text_wayback_language_benchmark_v2 import validate_benchmark


class VerifyExternalTextWaybackLanguageBenchmarkV2Tests(unittest.TestCase):
    def test_accepts_balanced_high_confidence_records(self):
        records = []
        for index, status in enumerate(("CONFIRMED", "LEGITIMATE"), start=1):
            text = f"text {index}"
            records.append({"benchmark_record_id": f"R{index}", "language_stratum": "ENGLISH", "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML", "ground_truth_status": status, "label_confidence": "HIGH", "artifact": {"visible_text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}, "review_provenance": {"source_candidate_id": f"C{index}", "primary_decision": status, "primary_confidence": "HIGH", "second_decision": status, "second_confidence": "HIGH", "independent_human_second_review": False}, "training_eligible": False})
        benchmark = {"status": "OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING", "training_eligible": False, "model_input_contract": {"allowed_input": "artifact.visible_text only", "warning_or_registry_evidence_as_model_input_allowed": False}, "records": records}
        self.assertEqual(validate_benchmark(benchmark, 2), {"CONFIRMED": 1, "LEGITIMATE": 1})


if __name__ == "__main__":
    unittest.main()
