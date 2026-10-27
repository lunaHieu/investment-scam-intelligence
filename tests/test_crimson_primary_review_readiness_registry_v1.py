import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "crimson_primary_review_readiness_v1.json"


class CrimsonPrimaryReviewReadinessRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_counts_and_safety_reproduce(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in value["inputs"] + value["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        for item in value["outputs"]:
            path = Path(item["path"])
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(sha256_file(path), item["sha256"], item["role"])
        self.assertEqual(value["result"]["pending_primary_tasks"], 39)
        self.assertEqual(value["result"]["ready_for_truthful_human_primary_review"], 24)
        self.assertEqual(value["result"]["official_reference_followup_required"], 15)
        self.assertEqual(value["result"]["human_decisions_created"], 0)
        self.assertFalse(value["decision"]["ai_may_impersonate_human_reviewer"])
        self.assertFalse(value["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
