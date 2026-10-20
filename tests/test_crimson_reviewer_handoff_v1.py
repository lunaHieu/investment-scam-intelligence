import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "crimson_reviewer_handoff_v1.json"


class CrimsonReviewerHandoffV1Tests(unittest.TestCase):
    def test_handoff_pins_packets_and_preserves_human_boundary(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        counts = data["task_counts"]
        self.assertEqual(counts["pilot_population"], 40)
        self.assertEqual(counts["first_review_complete"], 1)
        self.assertEqual(counts["first_review_pending"], 39)
        self.assertEqual(counts["blind_second_ready"], 1)
        self.assertEqual(counts["blind_second_waiting"], 20)
        self.assertEqual(counts["official_reference_followup"], 15)

        rules = data["review_boundary"]
        self.assertTrue(rules["official_reference_urls_only"])
        self.assertTrue(rules["blind_second_must_be_independent"])
        self.assertFalse(rules["crimson_host_access_allowed"])
        self.assertFalse(rules["ai_may_impersonate_human_reviewer"])
        self.assertFalse(rules["labels_created"])
        self.assertFalse(rules["training_eligible"])


if __name__ == "__main__":
    unittest.main()
