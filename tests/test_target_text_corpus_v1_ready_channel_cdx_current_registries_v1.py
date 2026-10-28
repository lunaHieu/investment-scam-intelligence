import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_cdx_canary_result_v1.json"
BULK = ROOT / "registry" / "analyses" / "target_text_corpus_v1_ready_channel_cdx_bulk_release_v1.json"


def check_paths(test: unittest.TestCase, value: dict) -> None:
    for item in value.get("inputs", []) + value.get("implementation", []):
        path = ROOT / item["path"]
        test.assertTrue(path.is_file(), item["path"])
        test.assertEqual(sha256_file(path), item["sha256"], item["path"])
    for item in value.get("outputs", []):
        path = Path(item["path"])
        test.assertTrue(path.is_file(), item["role"])
        test.assertEqual(sha256_file(path), item["sha256"], item["role"])


class ReadyChannelCdxCurrentRegistriesV1Tests(unittest.TestCase):
    def test_canary_result_registry_hashes_and_safety(self) -> None:
        value = json.loads(CANARY.read_text(encoding="utf-8"))
        check_paths(self, value)
        self.assertEqual(value["result"]["network_requests"], 1)
        self.assertEqual(value["result"]["eligible_rows"], 2)
        self.assertFalse(value["decision"]["canary_rerun_allowed"])
        self.assertFalse(value["decision"]["capture_allowed"])

    def test_bulk_release_registry_hashes_population_and_safety(self) -> None:
        value = json.loads(BULK.read_text(encoding="utf-8"))
        check_paths(self, value)
        self.assertEqual(value["result"]["target_rows"], 68)
        self.assertEqual(value["result"]["network_requests_executed"], 0)
        self.assertTrue(value["decision"]["separate_execution_invocation_required"])
        self.assertFalse(value["decision"]["capture_allowed"])


if __name__ == "__main__":
    unittest.main()
