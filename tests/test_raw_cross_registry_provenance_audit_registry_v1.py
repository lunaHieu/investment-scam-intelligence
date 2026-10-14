import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "raw_cross_registry_provenance_audit_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RawCrossRegistryProvenanceAuditRegistryV1Tests(unittest.TestCase):
    def test_registered_artifacts_and_frozen_findings(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_PASS_PARTIAL_PROVENANCE_GAPS_PRESERVED")
        self.assertEqual(data["findings"]["raw_file_count"], 278)
        self.assertEqual(data["findings"]["verified_hash_pinned_chain_files"], 191)
        self.assertEqual(data["findings"]["no_hash_pinned_chain_found_files"], 87)
        self.assertEqual(data["findings"]["existing_raw_hash_mismatch_files"], 0)
        self.assertFalse(data["decision"]["complete_raw_provenance_chain_established"])
        self.assertFalse(data["decision"]["validation_or_test_opening_allowed"])
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
