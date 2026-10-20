import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "research_methodology_progress_v1.json"


class ResearchMethodologyProgressV1Tests(unittest.TestCase):
    def test_narrative_uses_verified_counts_and_keeps_model_gates_closed(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        progress = data["progress_vector"]
        self.assertEqual(progress["verified_existing_raw_files"], 278)
        self.assertEqual(progress["historical_train_rows"], 3916)
        self.assertEqual(progress["fresh_admitted_groups"], 0)
        self.assertEqual(progress["fresh_required_groups"], 300)
        self.assertEqual(progress["sec_iapd_availability_resolved"], 113)
        self.assertEqual(progress["sec_iapd_availability_planned"], 115)
        self.assertEqual(progress["sec_iapd_capture_plan_rows"], 58)
        self.assertEqual(progress["crimson_first_review_complete"], 1)
        self.assertEqual(progress["crimson_first_review_pending"], 39)
        self.assertEqual(progress["verified_vietnamese_supply"], 0)
        self.assertEqual(progress["usable_image_assets"], 0)

        decision = data["decision"]
        self.assertFalse(decision["single_overall_percentage_valid"])
        self.assertFalse(decision["validation_or_test_opening_allowed"])
        self.assertFalse(decision["training_allowed"])
        self.assertFalse(decision["model_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
