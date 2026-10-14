import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "raw_source_manifest_coverage_audit_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RawSourceManifestCoverageAuditRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_passed_partial_coverage_without_opening_gates(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])

        findings = registry["findings"]
        self.assertEqual(findings["supported_manifest_count"], 37)
        self.assertEqual(findings["missing_registered_files"], 0)
        self.assertEqual(findings["registered_hash_mismatches"], 0)
        self.assertEqual(findings["raw_inventory_file_count"], 278)
        self.assertEqual(findings["outside_source_manifest_scope_files"], 241)
        self.assertTrue(registry["decision"]["registered_source_manifest_integrity_passed"])
        self.assertFalse(registry["decision"]["complete_raw_provenance_coverage_claim_allowed"])
        for gate in ("training_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed"):
            self.assertFalse(registry["decision"][gate])


if __name__ == "__main__":
    unittest.main()
