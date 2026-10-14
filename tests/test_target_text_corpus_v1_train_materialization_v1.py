import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_group_split_plan_v1 import build as build_split
from scripts.build_target_text_corpus_v1_train_materialization_release_v1 import build as build_release
from scripts.materialize_target_text_corpus_v1_train_only_v1 import materialize
from scripts.verify_target_text_corpus_v1_core_release_v1 import verify as verify_core_release
from scripts.verify_target_text_corpus_v1_group_split_plan_v1 import verify as verify_split
from scripts.verify_target_text_corpus_v1_train_materialization_release_v1 import verify as verify_release
from scripts.verify_target_text_corpus_v1_train_only_result_v1 import verify as verify_result
from tests import test_verify_target_text_corpus_v1_core_release_v1 as core_helpers


ROOT = Path(__file__).resolve().parents[1]
CORE_CONTRACT = ROOT / "configs" / "target_text_corpus_v1_core_release_contract_v1.json"
SPLIT_CONTRACT = ROOT / "configs" / "target_text_corpus_v1_group_split_contract_v1.json"
TRAIN_CONTRACT = ROOT / "configs" / "target_text_corpus_v1_train_materialization_contract_v1.json"


class TargetTextCorpusV1TrainMaterializationTests(unittest.TestCase):
    def make_release(self, directory: Path) -> tuple[Path, Path, Path, Path]:
        manifest_path = core_helpers.TargetTextCorpusV1CoreReleaseVerifierTests().make_manifest(directory)
        core_qa = verify_core_release(CORE_CONTRACT, manifest_path)
        core_qa_path = directory / "core_release_qa.json"
        core_qa_path.write_text(json.dumps(core_qa, indent=2) + "\n", encoding="utf-8")
        split = build_split(SPLIT_CONTRACT, manifest_path, core_qa_path)
        split_path = directory / "split_plan.json"
        split_path.write_text(json.dumps(split, indent=2) + "\n", encoding="utf-8")
        split_qa = verify_split(split_path)
        split_qa_path = directory / "split_qa.json"
        split_qa_path.write_text(json.dumps(split_qa, indent=2) + "\n", encoding="utf-8")
        dataset_path = directory / "train_only.jsonl"
        report_path = directory / "train_only_report.json"
        release = build_release(
            TRAIN_CONTRACT,
            split_path,
            split_qa_path,
            dataset_path,
            report_path,
            "2026-10-14T12:00:00+07:00",
        )
        release_path = directory / "train_materialization_release.json"
        release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
        release_qa = verify_release(release_path)
        self.assertEqual(release_qa["status"], "PASS_TRAIN_ONLY_RELEASE_REPRODUCED_EXECUTION_MAY_PROCEED")
        release_qa_path = directory / "train_materialization_release_qa.json"
        release_qa_path.write_text(json.dumps(release_qa, indent=2) + "\n", encoding="utf-8")
        return release_path, release_qa_path, dataset_path, report_path

    def write_materialization(self, release_path: Path, release_qa_path: Path, dataset_path: Path, report_path: Path) -> None:
        _, report, payload = materialize(release_path, release_qa_path)
        dataset_path.write_bytes(payload)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_release_contains_exactly_train_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, _, _, _ = self.make_release(Path(tmp))
            release = json.loads(release_path.read_text(encoding="utf-8"))
            self.assertEqual(release["summary"]["record_count"], 168)
            self.assertEqual(release["summary"]["label_counts"], {"CONFIRMED": 84, "LEGITIMATE": 84})
            self.assertEqual(set(release["summary"]["channel_counts"].values()), {42})
            self.assertEqual(release["summary"]["validation_records"], 0)
            self.assertFalse(release["decision"]["training_allowed"])

    def test_materialization_has_only_four_model_dataset_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_path, release_qa_path, _, _ = self.make_release(Path(tmp))
            rows, report, _ = materialize(release_path, release_qa_path)
            self.assertEqual(len(rows), 168)
            self.assertTrue(all(set(row) == {"record_id", "text_content", "label", "group_id"} for row in rows))
            self.assertEqual({row["label"] for row in rows}, {0, 1})
            self.assertEqual(report["summary"]["validation_records"], 0)
            self.assertFalse(report["decision"]["training_allowed_now"])

    def test_materialized_result_is_independently_reproduced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.make_release(Path(tmp))
            self.write_materialization(*inputs)
            qa = verify_result(inputs[2], inputs[3], inputs[0], inputs[1])
            self.assertEqual(qa["status"], "PASS_TRAIN_ONLY_DATASET_REPRODUCED_MODEL_PROTOCOL_REQUIRED")
            self.assertFalse(qa["decision"]["training_allowed_now"])

    def test_tampered_dataset_fails_result_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.make_release(Path(tmp))
            self.write_materialization(*inputs)
            lines = inputs[2].read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[0])
            first["label"] = 1 - first["label"]
            lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
            inputs[2].write_text("\n".join(lines) + "\n", encoding="utf-8")
            qa = verify_result(inputs[2], inputs[3], inputs[0], inputs[1])
            self.assertEqual(qa["status"], "FAIL")

    def test_release_builder_refuses_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            release_path, release_qa_path, dataset_path, report_path = self.make_release(directory)
            dataset_path.write_text("occupied", encoding="utf-8")
            release = json.loads(release_path.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                build_release(
                    TRAIN_CONTRACT,
                    Path(release["inputs"]["split_plan"]["path"]),
                    Path(release["inputs"]["split_qa"]["path"]),
                    dataset_path,
                    report_path,
                    "2026-10-14T12:00:00+07:00",
                )
            self.assertTrue(release_qa_path.is_file())


if __name__ == "__main__":
    unittest.main()
