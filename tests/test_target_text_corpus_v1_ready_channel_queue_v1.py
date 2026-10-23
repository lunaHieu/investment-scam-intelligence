import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_ready_channel_queue_v1 import build, write_jsonl
from scripts.verify_target_text_corpus_v1_ready_channel_queue_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_ready_channel_queue_release_v1.json"


class ReadyChannelQueueV1Tests(unittest.TestCase):
    def test_release_builds_exact_disjoint_unlabeled_queue_offline(self) -> None:
        queue, report = build(CONFIG)
        self.assertEqual(len(queue), 70)
        self.assertEqual(report["status"], "PASS_EXACT_70_PROVENANCE_QUEUE_CREATED_CAPTURE_CLOSED")
        self.assertEqual(len({row["candidate_id"] for row in queue}), 70)
        self.assertEqual(len({row["candidate_identity"]["normalized_host"] for row in queue}), 70)
        self.assertEqual(len({row["candidate_identity"]["normalized_entity"] for row in queue}), 70)
        self.assertEqual(sum(row["cohort"] == "DEVELOPMENT" for row in queue), 50)
        self.assertEqual(sum(row["cohort"] == "EXTERNAL_HOLDOUT" for row in queue), 20)
        self.assertTrue(all(row["review_state"]["ground_truth_status"] == "UNCERTAIN" for row in queue))
        self.assertTrue(all(row["review_state"]["label_created"] is False for row in queue))
        self.assertTrue(all(row["safety"]["wayback_queried"] is False for row in queue))
        self.assertEqual(report["safety_contract"]["network_operations"], 0)

    def test_open_network_gate_is_rejected(self) -> None:
        release = json.loads(CONFIG.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(release)
        tampered["decision"]["network_access_allowed"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(tampered, handle)
            path = Path(handle.name)
        try:
            with self.assertRaisesRegex(PermissionError, "network_access_allowed"):
                build(path)
        finally:
            path.unlink(missing_ok=True)

    def test_independent_verifier_rejects_membership_tampering(self) -> None:
        queue, report = build(CONFIG)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "queue.jsonl"
            report_path = root / "report.json"
            write_jsonl(queue_path, queue)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            passed = verify(CONFIG, queue_path, report_path)
            self.assertEqual(passed["status"], "PASS_EXACT_70_QUEUE_REPRODUCED_CAPTURE_REMAINS_CLOSED")

            tampered = copy.deepcopy(queue)
            tampered[0]["candidate_identity"]["normalized_host"] = "tampered.invalid"
            write_jsonl(queue_path, tampered)
            failed = verify(CONFIG, queue_path, report_path)
            self.assertEqual(failed["status"], "FAIL")
            self.assertTrue(any("independent recomputation" in error for error in failed["errors"]))


if __name__ == "__main__":
    unittest.main()
