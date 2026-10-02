import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_target_text_corpus_v1_preacquisition.py"
PROTOCOL_PATH = REPO_ROOT / "configs" / "target_text_corpus_v1_preacquisition_protocol.json"
SPEC = importlib.util.spec_from_file_location("target_text_corpus_v1_preacquisition", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TargetTextCorpusV1PreacquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = MODULE.load_json(PROTOCOL_PATH)

    def test_protocol_is_hash_pinned_and_offline(self):
        for item in self.protocol["inputs"]:
            path = MODULE.resolve(REPO_ROOT, item["path"])
            self.assertEqual(MODULE.sha256_file(path), item["sha256"])
        safety = self.protocol["safety_contract"]
        self.assertEqual(safety["network_operations"], 0)
        self.assertFalse(safety["domain_access_allowed"])
        self.assertEqual(safety["new_records_acquired"], 0)
        self.assertFalse(safety["training_allowed"])

    def test_candidate_inventory_is_provenance_only_and_reports_gaps(self):
        sources = MODULE.load_json(REPO_ROOT / "registry" / "sources.json")
        inventory = MODULE.build_candidate_inventory(self.protocol, sources)
        self.assertEqual(inventory["record_count"], 0)
        self.assertEqual(len(inventory["channels"]), 4)
        self.assertFalse(inventory["coverage"]["channel_gate_passed"])
        self.assertEqual(inventory["coverage"]["missing_registered_source_ids"], [])
        self.assertEqual(inventory["safety_contract"]["artifact_text_emitted"], 0)

    def test_exclusion_index_covers_all_opened_records_without_labels_or_text(self):
        index = MODULE.build_exclusion_index(self.protocol, REPO_ROOT)
        self.assertEqual(index["counts"]["cohorts"], 4)
        self.assertEqual(index["counts"]["opened_records"], 107)
        self.assertEqual(index["counts"]["unique_capture_sha256"], 98)
        self.assertEqual(index["counts"]["unique_text_sha256"], 96)
        self.assertEqual(index["counts"]["unique_normalized_host_sha256"], 94)
        self.assertEqual(index["counts"]["records_with_case_id"], 21)
        self.assertEqual(index["counts"]["records_missing_case_id"], 86)
        self.assertTrue(
            index["quality_gates"]["exact_and_normalized_host_exclusion_ready"]
        )
        self.assertFalse(
            index["quality_gates"][
                "case_domain_family_and_normalized_near_duplicate_exclusion_ready"
            ]
        )
        serialized_records = json.dumps(index["records"])
        self.assertNotIn("ground_truth_status", serialized_records)
        self.assertNotIn("visible_text", serialized_records)
        self.assertNotIn('"text":', serialized_records)

    def test_wayback_url_resolves_original_host(self):
        artifact = {
            "url": "https://web.archive.org/web/20260704070023id_/https://www.example.com/path"
        }
        self.assertEqual(MODULE.normalized_original_host(artifact), "example.com")


if __name__ == "__main__":
    unittest.main()
