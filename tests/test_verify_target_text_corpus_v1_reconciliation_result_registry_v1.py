import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_reconciliation_result_registry_v1 import verify


ROOT = Path(__file__).resolve().parents[1]


class TargetTextCorpusReconciliationResultRegistryTests(unittest.TestCase):
    def test_registered_result_passes(self) -> None:
        errors = verify(ROOT / "registry" / "analyses" / "target_text_corpus_v1_reconciliation_result_v1.json")
        self.assertFalse(errors, errors)


if __name__ == "__main__":
    unittest.main()
