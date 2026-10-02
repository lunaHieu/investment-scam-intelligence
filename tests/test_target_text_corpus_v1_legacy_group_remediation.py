import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "build_target_text_corpus_v1_legacy_group_remediation.py"
)
PROTOCOL_PATH = (
    REPO_ROOT / "configs" / "target_text_corpus_v1_legacy_group_remediation_v1.json"
)
SPEC = importlib.util.spec_from_file_location("legacy_group_remediation", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class LegacyGroupRemediationTests(unittest.TestCase):
    def test_group_id_is_order_independent(self):
        first = MODULE.group_id(["B", "A"])
        second = MODULE.group_id(["A", "B"])
        self.assertEqual(first, second)
        self.assertRegex(first, r"^LEGX_[0-9A-F]{16}$")

    def test_components_are_transitive_across_exact_keys(self):
        records = [
            {
                "record_exclusion_key": "A",
                "capture_sha256": "capture-a",
                "text_sha256": "text-a",
                "normalized_host_sha256": "host-a",
            },
            {
                "record_exclusion_key": "B",
                "capture_sha256": "capture-a",
                "text_sha256": "text-b",
                "normalized_host_sha256": "host-b",
            },
            {
                "record_exclusion_key": "C",
                "capture_sha256": "capture-c",
                "text_sha256": "text-b",
                "normalized_host_sha256": "host-c",
            },
        ]
        components = MODULE.build_components(records)
        self.assertEqual(list(components.values()), [["A", "B", "C"]])

    def test_canonical_queue_hash_ignores_key_order(self):
        self.assertEqual(
            MODULE.canonical_record_sha256({"b": 2, "a": 1}),
            MODULE.canonical_record_sha256({"a": 1, "b": 2}),
        )

    def test_protocol_forbids_case_and_label_creation(self):
        protocol = MODULE.load_json(PROTOCOL_PATH)
        self.assertFalse(
            protocol["grouping_algorithm"]["formal_case_id_backfill_allowed"]
        )
        self.assertFalse(
            protocol["grouping_algorithm"][
                "source_case_id_promotion_to_formal_case_id_allowed"
            ]
        )
        self.assertEqual(protocol["safety_contract"]["labels_created"], 0)
        self.assertFalse(protocol["gate_policy"]["new_candidate_capture_allowed_after_this_step"])


if __name__ == "__main__":
    unittest.main()
