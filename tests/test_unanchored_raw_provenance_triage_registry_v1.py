import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "unanchored_raw_provenance_triage_v1.json"


class UnanchoredRawProvenanceTriageRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_and_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_PASS_GAPS_CLASSIFIED_NO_PROMOTION")
        self.assertEqual(data["findings"]["matching_unanchored_hash_evidence_files"], 87)
        self.assertEqual(data["findings"]["conflicting_unanchored_hash_evidence_files"], 0)
        self.assertEqual(data["findings"]["files_promoted"], 0)
        self.assertTrue(data["decision"]["retrospective_integrity_anchor_may_be_prepared"])
        self.assertFalse(data["decision"]["git_rooted_provenance_complete"])
        self.assertFalse(data["decision"]["training_allowed"])
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
