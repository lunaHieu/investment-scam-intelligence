import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_grouping_tooling_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdGroupingToolingRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_grouping_and_protects_holdout(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["opened_exclusion_rows"], 107)
        self.assertEqual(registry["findings"]["holdout_collision_policy"], "ROUTE_HOLDOUT_MEMBER_OUT_OF_INDEPENDENT_HOLDOUT")
        self.assertFalse(registry["decision"]["real_grouping_allowed_now"])
        self.assertFalse(registry["decision"]["primary_label_review_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
