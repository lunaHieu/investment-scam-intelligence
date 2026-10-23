import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_ready_channel_wayback_availability_plan_v1 import build_rows, planned_request_url
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_plan_v1 import decode_request, verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_plan_release_v1.json"


def write_fixture(directory: Path) -> tuple[Path, Path, list[dict], dict]:
    plan, report = build_rows(CONFIG)
    plan_path = directory / "plan.jsonl"
    report_path = directory / "report.json"
    plan_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in plan), encoding="utf-8")
    report["plan_sha256"] = sha256_file(plan_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan_path, report_path, plan, report


class ReadyChannelWaybackAvailabilityPlanV1Tests(unittest.TestCase):
    def test_exact_70_plan_is_disjoint_unexecuted_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan_path, report_path, plan, _ = write_fixture(Path(directory))
            result = verify(CONFIG, plan_path, report_path)
        self.assertEqual(result["status"], "PASS_EXACT_70_AVAILABILITY_PLAN_INDEPENDENTLY_REPRODUCED_NETWORK_CLOSED")
        self.assertEqual(result["checks"]["plan_rows"], 70)
        self.assertEqual(result["checks"]["development_rows"], 50)
        self.assertEqual(result["checks"]["external_holdout_rows"], 20)
        self.assertEqual(result["checks"]["development_holdout_host_overlap"], 0)
        self.assertEqual(result["checks"]["development_holdout_entity_overlap"], 0)
        self.assertTrue(result["checks"]["candidate_order_preserved"])
        self.assertTrue(result["checks"]["planned_request_urls_round_trip"])
        self.assertEqual(result["checks"]["future_minimum_delay_seconds"], 60.0)
        self.assertTrue(all(row["wayback_queried"] is False for row in plan))
        self.assertTrue(all(row["ground_truth_status"] == "UNCERTAIN" for row in plan))

    def test_planned_request_encodes_candidate_but_targets_only_archive(self) -> None:
        value = planned_request_url("https://archive.org/wayback/available", "https://example.test/invest?q=one", "20261003")
        decoded_url, timestamp = decode_request(value)
        self.assertEqual(decoded_url, "https://example.test/invest?q=one")
        self.assertEqual(timestamp, "20261003")
        self.assertTrue(value.startswith("https://archive.org/wayback/available?"))

    def test_open_network_gate_is_rejected(self) -> None:
        release = json.loads(CONFIG.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(release)
        tampered["decision"]["network_execution_allowed"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(tampered, handle)
            path = Path(handle.name)
        try:
            with self.assertRaisesRegex(PermissionError, "network_execution_allowed"):
                build_rows(path)
        finally:
            path.unlink(missing_ok=True)

    def test_independent_verifier_rejects_request_url_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path, report_path, plan, report = write_fixture(root)
            plan[0]["planned_request_url"] = "https://example.test/wayback/available?url=x&timestamp=20261003"
            plan_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in plan), encoding="utf-8")
            report["plan_sha256"] = sha256_file(plan_path)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = verify(CONFIG, plan_path, report_path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("request URL invalid" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
