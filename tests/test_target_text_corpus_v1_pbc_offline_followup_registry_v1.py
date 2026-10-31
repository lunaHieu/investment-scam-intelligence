import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "registry/analyses/target_text_corpus_v1_pbc_offline_followup_v1.json"


class PbcOfflineFollowupRegistryV1Tests(unittest.TestCase):
    def test_analysis_hashes_and_conservative_findings(self):
        data = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["status"], "PASS_SYNTHETIC_BOUNDARIES_CHECKED_LIVE_EXACT_CAUSES_REMAIN_UNRECOVERABLE")
        self.assertFalse(data["pbc05"]["retry_allowed"])
        self.assertFalse(data["pbc05"]["raw_pdf_or_stderr_recovered"])
        self.assertFalse(data["pbc08"]["retry_allowed"])
        self.assertEqual(data["pbc08"]["exact_live_key_status"], "NOT_IDENTIFIABLE_FROM_RETAINED_RESULT")
        self.assertEqual(data["execution"]["focused_synthetic_tests_passed"], 5)
        self.assertEqual(data["execution"]["focused_registry_tests_passed"], 3)
        self.assertEqual(data["execution"]["current_full_suite"]["passed"], 1167)
        self.assertEqual(data["execution"]["current_full_suite"]["failed"], 0)
        self.assertEqual(data["execution"]["registry_validation"]["analysis_registries"], 399)
        self.assertEqual(data["execution"]["source_endpoint_requests"], 0)
        self.assertEqual(data["execution"]["dataset_rows_or_labels_created"], 0)


if __name__ == "__main__":
    unittest.main()
