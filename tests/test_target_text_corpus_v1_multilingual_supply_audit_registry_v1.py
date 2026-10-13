import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_multilingual_supply_audit_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusV1MultilingualSupplyAuditRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_zero_verified_supply_and_closed_gate(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["audited_rows"], 16504)
        self.assertEqual(registry["findings"]["unknown_language_rows"], 16504)
        self.assertEqual(registry["findings"]["verified_vietnamese_rows"], 0)
        self.assertFalse(registry["decision"]["language_supply_gate_met"])
        self.assertFalse(registry["decision"]["candidate_release_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
