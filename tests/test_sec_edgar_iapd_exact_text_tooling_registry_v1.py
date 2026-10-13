import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_exact_text_tooling_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdExactTextToolingRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_offline_tooling_and_keeps_labels_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["minimum_non_whitespace_text_characters"], 20)
        self.assertTrue(registry["findings"]["independent_byte_regeneration_required"])
        self.assertFalse(registry["decision"]["real_extraction_allowed_now"])
        self.assertFalse(registry["decision"]["labeling_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
