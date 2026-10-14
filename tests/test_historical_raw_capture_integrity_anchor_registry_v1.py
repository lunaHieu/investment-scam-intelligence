import hashlib
import json
import unittest
from pathlib import Path

from scripts.verify_historical_raw_capture_integrity_anchor_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "historical_raw_capture_integrity_anchor_v1.json"


class HistoricalRawCaptureIntegrityAnchorRegistryV1Tests(unittest.TestCase):
    def test_frozen_anchor_and_implementation_hashes(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "FROZEN_RETROSPECTIVE_INTEGRITY_ANCHOR_NO_PROMOTION")
        self.assertEqual(data["findings"]["anchored_evidence_document_count"], 11)
        self.assertEqual(data["findings"]["covered_previously_unanchored_raw_files"], 87)
        self.assertEqual(data["decision"]["files_promoted"], 0)
        self.assertFalse(data["decision"]["training_allowed"])
        for item in data["inputs"] + data["evidence_documents"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertEqual(verify(REGISTRY)["status"], "PASS_HISTORICAL_CAPTURE_INTEGRITY_ANCHOR_VERIFIED")


if __name__ == "__main__":
    unittest.main()
