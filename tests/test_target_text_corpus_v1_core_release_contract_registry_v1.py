import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_core_release_contract_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusV1CoreReleaseContractRegistryTests(unittest.TestCase):
    def test_registry_pins_balanced_release_validator_and_keeps_models_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["required_total_groups"], 300)
        self.assertEqual(registry["findings"]["required_development_groups"], 240)
        self.assertEqual(registry["findings"]["required_external_holdout_groups"], 60)
        self.assertTrue(registry["findings"]["cross_cohort_group_overlap_forbidden"])
        self.assertFalse(registry["decision"]["actual_dataset_release_allowed_now"])
        self.assertFalse(registry["decision"]["training_allowed"])
        self.assertFalse(registry["decision"]["validation_or_test_opening_allowed"])


if __name__ == "__main__":
    unittest.main()
