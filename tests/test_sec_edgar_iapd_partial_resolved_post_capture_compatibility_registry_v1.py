import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_partial_resolved_post_capture_compatibility_v1.json"


class SecEdgarIapdPartialResolvedPostCaptureCompatibilityRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_58_row_compatibility_evidence_and_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["compatible_capture_rows"], 58)
        self.assertEqual(data["findings"]["compatible_by_cohort"], {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12})
        self.assertTrue(data["decision"]["existing_exact_text_v1_compatible"])
        self.assertTrue(data["decision"]["existing_grouping_release_v1_compatible"])
        self.assertFalse(data["decision"]["real_extraction_allowed_now"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
