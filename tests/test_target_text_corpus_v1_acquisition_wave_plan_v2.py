import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_acquisition_wave_plan_v2 import verify


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "configs" / "target_text_corpus_v1_acquisition_wave_plan_v2.json"


class AcquisitionWavePlanV2Tests(unittest.TestCase):
    def test_plan_preserves_residual_targets_and_closed_gates(self) -> None:
        result = verify(PLAN)
        self.assertEqual(result["status"], "PASS_OFFLINE_WAVE_PLAN_SOURCE_GATES_CLOSED")
        self.assertEqual(result["checks"]["development_residual_target"], 207)
        self.assertEqual(result["checks"]["external_holdout_residual_target"], 51)
        self.assertEqual(result["checks"]["owner_accepted_candidate_supply"], 42)
        self.assertFalse(result["decision"]["network_allowed_now"])
        self.assertFalse(result["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
