import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_target_text_corpus_v1_wayback_availability_retry_v2.py"
SPEC = importlib.util.spec_from_file_location("wayback_retry_v2_verifier", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WaybackAvailabilityRetryV2VerifierTests(unittest.TestCase):
    def test_frozen_retry_registry_passes(self) -> None:
        registry = (
            ROOT
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_wayback_availability_retry_v2.json"
        )
        result = MODULE.verify_registry(registry)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["retry_candidate_count"], 31)
        self.assertFalse(result["candidate_capture_allowed"])


if __name__ == "__main__":
    unittest.main()
