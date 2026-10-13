import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_vietnamese_channel_terms_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusV1VietnameseChannelTermsRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_source_roles_and_keeps_acquisition_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["source_count"], 2)
        self.assertEqual(registry["findings"]["target_status_count"], 2)
        self.assertTrue(registry["decision"]["source_role_registration_gate_passed"])
        self.assertFalse(registry["decision"]["reference_acquisition_gate_passed"])
        self.assertTrue(registry["decision"]["sampling_matrix_v2_required"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
