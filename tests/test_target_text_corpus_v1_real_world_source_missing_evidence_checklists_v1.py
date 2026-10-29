import unittest

from scripts.verify_target_text_corpus_v1_real_world_source_missing_evidence_checklists_v1 import verify


class RealWorldSourceMissingEvidenceChecklistsV1Tests(unittest.TestCase):
    def test_checklists_are_complete_and_nonacquiring(self) -> None:
        self.assertEqual(verify(), {"status":"PASS_MISSING_EVIDENCE_CHECKLISTS","sources":2,"requirements":14})


if __name__ == "__main__":
    unittest.main()
