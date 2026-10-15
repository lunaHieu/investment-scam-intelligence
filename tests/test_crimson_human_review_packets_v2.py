import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_crimson_human_review_packets_v2 import load_jsonl, materialize
from scripts.verify_crimson_human_review_packets_v2 import verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "crimson_human_review_packets_v2.json"
REGISTRY = ROOT / "registry" / "analyses" / "crimson_human_review_packets_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CrimsonHumanReviewPacketsV2Tests(unittest.TestCase):
    def test_packets_are_recomputed_disjoint_tasks_and_blind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = materialize(CONFIG, root)
            self.assertEqual(report["counts"]["first_review_pending"], 39)
            self.assertEqual(report["counts"]["blind_second_review_ready"], 1)
            self.assertEqual(report["counts"]["blind_second_review_waiting"], 20)
            self.assertEqual(report["counts"]["official_reference_followup"], 15)
            self.assertEqual(report["second_review_population"], 21)
            ready = load_jsonl(root / "blind_second_review_ready_v2.jsonl")
            waiting = load_jsonl(root / "blind_second_review_waiting_v2.jsonl")
            forbidden = {
                "identity_suggestion",
                "evidence_suggestion",
                "first_reviewer",
                "first_review_decision",
                "first_review_notes",
            }
            self.assertEqual(ready[0]["pilot_id"], "PILOT_CRIMSON_REF_018")
            self.assertTrue(all(not forbidden.intersection(row) for row in ready + waiting))
            task_ids = []
            for filename in (
                "first_review_pending_v2.jsonl",
                "blind_second_review_ready_v2.jsonl",
                "blind_second_review_waiting_v2.jsonl",
                "official_reference_followup_v2.jsonl",
            ):
                task_ids.extend(row["task_id"] for row in load_jsonl(root / filename))
            self.assertEqual(len(task_ids), len(set(task_ids)))
            result = verify(CONFIG, root)
            self.assertTrue(result["valid"])
            self.assertEqual(result["human_decisions_created"], 0)
            self.assertEqual(result["labels_created"], 0)

    def test_builder_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(CONFIG, root)
            with self.assertRaises(FileExistsError):
                materialize(CONFIG, root)

    def test_registry_hashes_and_closed_gates_are_current(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["first_review_pending"], 39)
        self.assertEqual(data["findings"]["live_reference_followup"], 15)
        self.assertFalse(data["decision"]["human_decisions_created"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
