import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_review_stack_tooling_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdReviewStackToolingRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_blind_review_and_owner_acceptance_gate(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertTrue(registry["findings"]["primary_source_membership_alone_insufficient"])
        self.assertTrue(registry["findings"]["blind_second_review_required"])
        self.assertTrue(registry["findings"]["any_disagreement_becomes_uncertain"])
        self.assertFalse(registry["decision"]["real_review_allowed_now"])
        self.assertTrue(registry["decision"]["future_owner_acceptance_required"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
