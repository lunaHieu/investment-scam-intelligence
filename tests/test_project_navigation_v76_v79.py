from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPRO = ROOT / "registry/analyses/reproducibility_current_state_v76.json"
LEDGER = ROOT / "registry/analyses/project_state_gap_ledger_v79.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_artifact(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def assert_pinned_files(test: unittest.TestCase, items: list[dict]) -> None:
    for item in items:
        path = resolve_artifact(item["path"])
        test.assertTrue(path.is_file(), item["path"])
        test.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])


class ProjectNavigationV76V79Tests(unittest.TestCase):
    def test_current_reproducibility_artifacts_are_hash_pinned(self) -> None:
        data = load(REPRO)
        assert_pinned_files(self, data["inputs"] + data["implementation"] + data["outputs"])

    def test_gap_ledger_links_to_verified_current_state(self) -> None:
        data = load(LEDGER)
        assert_pinned_files(self, data["inputs"])
        self.assertEqual(data["state"]["crimson"]["primary_review_open"], 15)
        self.assertEqual(data["state"]["crimson"]["new_v3_pilot_id"], "PILOT_CRIMSON_REF_016")
        self.assertEqual(data["state"]["verification"]["current_full_suite_passed"], 1206)
        self.assertEqual(data["state"]["verification"]["analysis_registry_count"], 422)

    def test_review_and_training_gates_remain_closed(self) -> None:
        repro = load(REPRO)
        ledger = load(LEDGER)
        self.assertFalse(repro["decision"]["primary_review_of_v3_fact_completed"])
        self.assertFalse(repro["decision"]["independent_blind_second_review_completed"])
        self.assertFalse(repro["decision"]["training_allowed"])
        self.assertFalse(ledger["decision"]["data_admission_allowed"])
        self.assertFalse(ledger["decision"]["label_materialization_allowed"])


if __name__ == "__main__":
    unittest.main()
