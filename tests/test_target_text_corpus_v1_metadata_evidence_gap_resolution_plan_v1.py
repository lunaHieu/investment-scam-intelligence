import unittest

from scripts.verify_target_text_corpus_v1_metadata_evidence_gap_resolution_plan_v1 import verify


class MetadataEvidenceGapResolutionPlanV1Tests(unittest.TestCase):
    def test_plan_routes_seven_tasks_without_authorizing_execution(self) -> None:
        self.assertEqual(verify(), {"status":"PASS_GAP_RESOLUTION_PLAN_VERIFIED","lanes":3,"tasks":7,"lane_a_tasks":4})


if __name__ == "__main__":
    unittest.main()
