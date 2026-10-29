import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "configs" / "target_text_corpus_v1_sanitized_text_source_discovery_spec_v1.json"


class SanitizedTextSourceDiscoverySpecV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.value = json.loads(SPEC.read_text(encoding="utf-8"))

    def test_inputs_are_hash_bound(self) -> None:
        for item in self.value["inputs"]:
            self.assertEqual(hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest(), item["sha256"])

    def test_search_is_bounded_and_cannot_download(self) -> None:
        limits = self.value["future_network_release_limits"]
        self.assertLessEqual(limits["maximum_search_queries"], 12)
        self.assertLessEqual(limits["maximum_shortlisted_sources"], 20)
        self.assertIn("download source bytes", limits["forbidden_actions"])
        self.assertIn("open candidate live domains", limits["forbidden_actions"])

    def test_spec_does_not_open_execution_or_model_gates(self) -> None:
        decision = self.value["decision"]
        self.assertTrue(decision["bounded_discovery_release_may_be_prepared"])
        for key in ("network_execution_allowed_by_this_specification", "source_download_allowed", "candidate_live_domain_access_allowed", "labeling_allowed", "training_allowed"):
            self.assertFalse(decision[key])


if __name__ == "__main__":
    unittest.main()
