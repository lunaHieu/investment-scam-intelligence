import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_group_split_contract_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusV1GroupSplitContractRegistryTests(unittest.TestCase):
    def test_registry_pins_deterministic_split_and_sealed_holdout(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["train_assignments"], 168)
        self.assertEqual(registry["findings"]["validation_assignments"], 36)
        self.assertEqual(registry["findings"]["internal_test_assignments"], 36)
        self.assertEqual(registry["findings"]["external_holdout_records_sealed"], 60)
        self.assertTrue(registry["findings"]["split_independent_of_text_and_model_signals"])
        self.assertFalse(registry["decision"]["real_split_allowed_now"])
        self.assertFalse(registry["decision"]["training_allowed"])
        self.assertFalse(registry["decision"]["validation_or_test_opening_allowed"])


if __name__ == "__main__":
    unittest.main()
