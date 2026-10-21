import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_captured_subset_post_capture_v2.json"


class SecEdgarIapdCapturedSubsetPostCaptureRegistryV2Tests(unittest.TestCase):
    def test_registry_hashes_counts_and_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS_56_GROUP_APPROVED_PRIMARY_ARTIFACT_REVIEW_MAY_BE_PREPARED")
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(sha256_file(path), item["sha256"], item["role"])
        result = data["result"]
        self.assertEqual(result["source_capture_plan_rows"], 58)
        self.assertEqual(result["captured_subset_rows"], 57)
        self.assertEqual(result["exact_text_byte_reproduced_rows"], 57)
        self.assertEqual(result["reviewable_rows"], 56)
        self.assertEqual(result["manual_group_reviewed_rows"], 56)
        self.assertEqual(result["manual_group_decision_counts"], {"KEEP_PROVISIONALLY_DISTINCT": 56})
        self.assertEqual(result["labels_created"], 0)
        self.assertTrue(data["decision"]["primary_artifact_review_may_be_prepared"])
        self.assertFalse(data["decision"]["training_allowed"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])


if __name__ == "__main__":
    unittest.main()
