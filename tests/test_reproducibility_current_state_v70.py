import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry/analyses/reproducibility_current_state_v70.json"


class ReproducibilityCurrentStateV70Tests(unittest.TestCase):
    def test_current_guide_and_offline_diagnostics_are_hash_pinned(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + [data["output"]]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])

        self.assertEqual(data["current_entrypoint"], "registry/analyses/project_state_gap_ledger_v73.json")
        self.assertEqual(data["current_pbc_state"]["synthetic_boundary_tests_passed"], 5)
        self.assertFalse(data["current_pbc_state"]["PBC05"]["same_release_retry_allowed"])
        self.assertFalse(data["current_pbc_state"]["PBC08"]["same_release_retry_allowed"])
        self.assertFalse(data["decision"]["new_source_request_authorized"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
