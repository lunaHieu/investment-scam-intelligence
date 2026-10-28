import json
import unittest
from pathlib import Path

from scripts.run_current_test_suite_v2 import LIFECYCLE_REPLACEMENTS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "current_test_suite_lifecycle_v2.json"


class CurrentTestSuiteLifecycleRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_current_files_and_consumed_outputs(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "PASS_EXACT_SIX_PREEXECUTION_ASSERTIONS_SUPERSEDED_BY_POSTEXECUTION_CHECKS")
        for item in value["inputs"] + value["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        for item in value["consumed_outputs"]:
            path = Path(item["path"])
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(sha256_file(path), item["sha256"], item["role"])

    def test_registry_keeps_exclusion_surface_bounded(self) -> None:
        value = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(value["findings"]["historical_preexecution_test_methods"], 6)
        self.assertEqual(value["findings"]["postexecution_replacement_test_methods"], 6)
        self.assertEqual(len(LIFECYCLE_REPLACEMENTS), 6)
        self.assertFalse(value["decision"]["frozen_release_mutation_allowed"])


if __name__ == "__main__":
    unittest.main()
