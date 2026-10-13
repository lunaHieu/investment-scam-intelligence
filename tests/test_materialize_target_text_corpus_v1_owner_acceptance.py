import hashlib
import json
import unittest
from pathlib import Path

from scripts.materialize_target_text_corpus_v1_owner_acceptance import materialize


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusOwnerAcceptanceTests(unittest.TestCase):
    def test_materializes_decisive_labels_but_keeps_training_closed(self) -> None:
        result = materialize(
            ROOT / "configs" / "target_text_corpus_v1_owner_acceptance_v1.json"
        )
        self.assertEqual(
            result["summary"]["ground_truth_counts"],
            {"CONFIRMED": 4, "LEGITIMATE": 11, "UNCERTAIN": 7},
        )
        self.assertEqual(result["summary"]["decisive_labels_materialized"], 15)
        self.assertEqual(result["summary"]["training_eligible_records"], 0)
        self.assertTrue(result["decision"]["diagnostic_only"])
        self.assertFalse(result["decision"]["training_allowed"])
        self.assertTrue(all(row["training_eligible"] == "NO" for row in result["records"]))

    def test_uncertain_records_are_not_materialized(self) -> None:
        result = materialize(
            ROOT / "configs" / "target_text_corpus_v1_owner_acceptance_v1.json"
        )
        uncertain = [row for row in result["records"] if row["ground_truth_status"] == "UNCERTAIN"]
        self.assertEqual(len(uncertain), 7)
        self.assertTrue(all(not row["ground_truth_materialized"] for row in uncertain))

    def test_registered_inputs_and_output_are_hash_pinned(self) -> None:
        registry_path = (
            ROOT / "registry" / "analyses" / "target_text_corpus_v1_owner_acceptance_result_v1.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertFalse(registry["decision"]["training_allowed"])
        self.assertFalse(registry["decision"]["model_scoring_allowed"])
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
