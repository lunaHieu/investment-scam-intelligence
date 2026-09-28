import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_crimson_iosco_first_pass_review.py"
SPEC = importlib.util.spec_from_file_location("prepare_crimson_iosco_first_pass_review", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CrimsonIoscoFirstPassReviewTests(unittest.TestCase):
    def test_live_status_aggregation(self):
        self.assertEqual(MODULE.aggregate_live_status(["LIVE_CONFIRMED"]), "ALL_URLS_LIVE_CONFIRMED")
        self.assertEqual(
            MODULE.aggregate_live_status(["LIVE_CONFIRMED", "LIVE_NOT_CONFIRMED"]),
            "PARTIAL_URLS_LIVE_CONFIRMED",
        )
        self.assertEqual(
            MODULE.aggregate_live_status(["LIVE_NOT_CONFIRMED"]),
            "SNAPSHOT_ONLY_LIVE_NOT_CONFIRMED",
        )

    def test_identity_suggestion_detects_clone_and_imposter(self):
        self.assertEqual(MODULE.identity_suggestion([{"entity_name_keys": ["Example Clone"]}]), "IMPERSONATION_SUSPECTED")
        self.assertEqual(
            MODULE.identity_suggestion([{"warning_categories": {"detail": "Registered entity impersonators"}}]),
            "IMPERSONATION_SUSPECTED",
        )
        self.assertEqual(MODULE.identity_suggestion([{"entity_name_keys": ["Example"]}]), "SAME_ENTITY")


if __name__ == "__main__":
    unittest.main()
