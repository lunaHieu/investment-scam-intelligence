import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "raw_cross_registry_provenance_audit_v2.json"


class RawCrossRegistryProvenanceAuditRegistryV2Tests(unittest.TestCase):
    def test_complete_existing_raw_provenance_and_closed_model_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_PASS_COMPLETE_EXISTING_RAW_PROVENANCE")
        self.assertEqual(data["findings"]["verified_hash_pinned_chain_files"], 278)
        self.assertEqual(data["findings"]["no_hash_pinned_chain_found_files"], 0)
        self.assertEqual(data["findings"]["existing_raw_hash_mismatch_files"], 0)
        self.assertEqual(data["findings"]["missing_raw_claim_unique_target_count"], 2)
        self.assertTrue(data["decision"]["complete_existing_raw_file_provenance_chain"])
        self.assertFalse(data["decision"]["historical_missing_claim_targets_resolved"])
        self.assertFalse(data["decision"]["training_allowed"])
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
