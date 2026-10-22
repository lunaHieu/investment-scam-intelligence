import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_capacity_gap_v3.json"


class TargetTextCorpusV1CapacityGapV3Tests(unittest.TestCase):
    def test_gap_is_recomputed_from_owner_accepted_supply_and_frozen_matrix(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])

        owner_path = Path(data["inputs"][1]["path"])
        accepted = json.loads(owner_path.read_text(encoding="utf-8"))["records"]
        observed = Counter()
        for row in accepted:
            self.assertIn("_EDGAR_", row["record_id"])
            observed[(row["cohort"], "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE")] += 1
        self.assertEqual(observed[("DEVELOPMENT", "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE")], 33)
        self.assertEqual(observed[("EXTERNAL_HOLDOUT", "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE")], 9)

        gaps = data["conditional_planning_gap_if_all_accepted_candidates_pass_release"]
        self.assertEqual(gaps["development_remaining"], 207)
        self.assertEqual(gaps["external_holdout_remaining"], 51)
        self.assertEqual(gaps["total_remaining"], 258)
        self.assertEqual(data["contractual_release_progress"]["admitted_groups"], 0)
        self.assertEqual(data["contractual_release_progress"]["required_groups"], 300)
        self.assertFalse(data["decision"]["v1_core_release_ready"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
