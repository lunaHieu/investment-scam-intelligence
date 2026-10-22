import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "reproducibility_current_state_v13.json"


class ReproducibilityCurrentStateV13Tests(unittest.TestCase):
    def test_current_navigation_points_to_verified_cdx_release(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "CURRENT_CDX_RELEASE_FROZEN_NETWORK_NOT_EXECUTED")
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        state = data["current_state"]
        self.assertEqual(state["fresh_v1_core_admitted_groups"], 0)
        self.assertEqual(state["cdx_release_target_rows"], 1)
        self.assertFalse(state["cdx_network_executed"])
        self.assertFalse(data["decision"]["capture_authorized"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
