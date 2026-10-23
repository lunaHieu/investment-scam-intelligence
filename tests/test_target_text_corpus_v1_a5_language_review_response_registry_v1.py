import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_a5_language_review_response_preflight_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class A5LanguageReviewResponseRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_and_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "C3_PREFLIGHT_COMPLETE_TRUTHFUL_HUMAN_RESPONSE_PENDING")
        for section in ("inputs", "implementation", "outputs"):
            for item in data[section]:
                path = Path(item["path"])
                if not path.is_absolute():
                    path = ROOT / path
                self.assertTrue(path.is_file(), item["role"])
                self.assertEqual(sha256(path), item["sha256"], item["role"])
        self.assertEqual(data["result"]["template_records"], 42)
        self.assertEqual(data["result"]["human_decisions_materialized"], 0)
        self.assertFalse(data["decision"]["c3_human_response_complete"])
        self.assertEqual(data["decision"]["v1_core_admission_credit_now"], 0)
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
