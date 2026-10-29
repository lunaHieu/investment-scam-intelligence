import unittest

from scripts.verify_target_text_corpus_v1_nexvision_synthetic_auxiliary_source_registration_addendum_v1 import verify


class NexVisionSyntheticAuxiliarySourceRegistrationAddendumV1Tests(unittest.TestCase):
    def test_addendum_is_synthetic_only_and_nonactivating(self) -> None:
        self.assertEqual(verify(), {"status":"PASS_PROPOSED_SYNTHETIC_SOURCE_ADDENDUM","source_id":"nexvision_scamintel_2026","fresh_v1_core_credit":0})


if __name__ == "__main__":
    unittest.main()
