import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_mendeley_text_challenger_v4_preflight.py"
SPEC = importlib.util.spec_from_file_location("verify_semantic_v4", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SemanticChallengerV4PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = MODULE.read_json(MODULE.PROTOCOL_PATH)
        cls.manifest = MODULE.read_json(
            REPO_ROOT / cls.protocol["encoder"]["manifest_path"]
        )

    def test_protocol_boundaries_are_frozen(self):
        MODULE.validate_protocol_boundaries(self.protocol)

    def test_pinned_inputs_match(self):
        MODULE.validate_pinned_inputs(self.protocol)

    def test_snapshot_files_hash_and_structure(self):
        result = MODULE.validate_local_snapshot(self.protocol, self.manifest)
        self.assertTrue(result["structurally_complete"])
        self.assertEqual(result["tensor_count"], 200)
        self.assertEqual(result["actual_file_bytes"], 133466304)

    def test_only_one_encoder_is_selectable(self):
        reviewed = self.protocol["encoder_selection_audit"]["candidates_reviewed"]
        selected = [row for row in reviewed if row["decision"] == "SELECTED_AS_THE_ONLY_CHALLENGER"]
        self.assertEqual([row["repository"] for row in selected], ["intfloat/e5-small-v2"])
        self.assertFalse(self.protocol["development_design"]["encoder_search"])

    def test_no_pre_freeze_computation_is_claimed(self):
        safety = self.protocol["safety_contract"]
        smoke = self.manifest["offline_runtime_smoke_test"]
        self.assertEqual(safety["embedding_operations_before_protocol_freeze"], 0)
        self.assertEqual(safety["model_fit_operations_before_protocol_freeze"], 0)
        self.assertEqual(smoke["forward_passes"], 0)
        self.assertEqual(smoke["embeddings_computed"], 0)

    def test_protocol_json_round_trips(self):
        encoded = json.dumps(self.protocol, sort_keys=True)
        self.assertEqual(json.loads(encoded)["protocol_id"], self.protocol["protocol_id"])


if __name__ == "__main__":
    unittest.main()
