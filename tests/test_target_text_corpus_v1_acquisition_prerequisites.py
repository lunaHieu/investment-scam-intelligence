import json
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.verify_target_text_corpus_v1_acquisition_prerequisites import (
    validate_ledger,
    validate_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_acquisition_prerequisite_intake_v1.json"
EXAMPLE = ROOT / "configs" / "target_text_corpus_v1_acquisition_prerequisites_v1.example.json"


class TargetTextCorpusAcquisitionPrerequisiteTests(unittest.TestCase):
    def test_frozen_intake_protocol_passes(self):
        result = validate_protocol(PROTOCOL)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["ready_prerequisite_count"], 0)
        self.assertEqual(result["missing_prerequisite_count"], 2)
        self.assertFalse(result["contact_identity_exposed"])
        self.assertFalse(result["candidate_enumeration_allowed"])
        self.assertFalse(result["network_execution_allowed"])

    def test_example_ledger_is_blocked_and_contains_no_email_address(self):
        ledger = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(validate_ledger(ledger), [])
        self.assertNotIn("@", json.dumps(ledger, ensure_ascii=False))

    def test_ledger_rejects_premature_release(self):
        ledger = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        changed = deepcopy(ledger)
        changed["release_gate"]["candidate_enumeration_allowed"] = True
        errors = validate_ledger(changed)
        self.assertTrue(any("release gate" in error.lower() for error in errors))

    def test_ledger_rejects_public_contact_identity(self):
        ledger = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        changed = deepcopy(ledger)
        changed["prerequisites"][1]["required_action"] = "Contact person@example.org"
        errors = validate_ledger(changed)
        self.assertTrue(any("email address" in error.lower() for error in errors))

    def test_private_path_is_outside_public_repository(self):
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        private_path = Path(protocol["private_sec_file_contract"]["path"]).resolve()
        with self.assertRaises(ValueError):
            private_path.relative_to(ROOT.resolve())


if __name__ == "__main__":
    unittest.main()
