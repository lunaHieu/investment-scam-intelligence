import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_candidate_enumeration_tooling import (
    validate_tooling,
    verify_registry,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "isi" / "curation" / "target_text_candidate_enumeration.py"
CLI = ROOT / "scripts" / "enumerate_target_text_corpus_v1_candidates.py"
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_schema_review_pilot_v1.json"
LEDGER = Path(
    r"D:\nckh 2026-2027\ISI_Data\governance\target_text_corpus_v1"
) / "acquisition_prerequisite_ledger_v1.json"
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_candidate_enumeration_tooling_v1.json"


class VerifyTargetTextCandidateEnumerationToolingTests(unittest.TestCase):
    def test_tooling_is_offline_and_current_production_run_is_blocked(self):
        result = validate_tooling(MODULE, CLI, PROTOCOL, LEDGER)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["initial_candidate_target"], 40)
        self.assertEqual(result["channel_count"], 4)
        self.assertEqual(result["network_import_count"], 0)
        self.assertFalse(result["production_enumeration_allowed"])

    def test_checked_in_registry_verifies(self):
        result = verify_registry(REGISTRY)
        self.assertTrue(result["valid"], result["errors"])
        self.assertFalse(result["production_enumeration_allowed"])


if __name__ == "__main__":
    unittest.main()
