import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "manual_source_owner_checklist_v1.json"


class ManualSourceOwnerChecklistV1Tests(unittest.TestCase):
    def test_checklist_preserves_manual_acquisition_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        states = data["source_states"]
        self.assertEqual(states["dfpi_crypto_scam_tracker"], "USER_SUPPLIED_FIRST_PARTY_ARTIFACT_OR_EXPLICIT_OFFICIAL_EXPORT_ONLY")
        self.assertEqual(states["ssc_vietnam_investor_warnings"], "BLOCKED_PENDING_EXPLICIT_OFFICIAL_EXPORT_OR_WRITTEN_REUSE_BASIS")
        self.assertEqual(states["hnx_vietnam_issuer_profiles"], "BLOCKED_PENDING_EXPLICIT_OFFICIAL_EXPORT_OR_WRITTEN_REUSE_BASIS")

        decision = data["decision"]
        self.assertTrue(decision["owner_checklist_ready"])
        self.assertFalse(decision["source_acquisition_executed"])
        self.assertFalse(decision["candidate_enumeration_allowed"])
        self.assertFalse(decision["labels_allowed"])
        self.assertFalse(decision["training_allowed"])


if __name__ == "__main__":
    unittest.main()
