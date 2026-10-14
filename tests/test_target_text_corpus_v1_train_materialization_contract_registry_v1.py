import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_train_materialization_contract_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusV1TrainMaterializationContractRegistryTests(unittest.TestCase):
    def test_registry_pins_train_only_materialization_and_closed_model_gates(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["expected_train_records"], 168)
        self.assertEqual(registry["findings"]["expected_records_per_label"], 84)
        self.assertEqual(registry["findings"]["dataset_field_count"], 4)
        self.assertTrue(registry["findings"]["validation_internal_test_and_holdout_excluded"])
        self.assertFalse(registry["decision"]["real_materialization_allowed_now"])
        self.assertFalse(registry["decision"]["training_allowed"])
        self.assertFalse(registry["decision"]["validation_or_test_opening_allowed"])


if __name__ == "__main__":
    unittest.main()
