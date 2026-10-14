import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_group_split_plan_v1 import build, canonical
from scripts.verify_target_text_corpus_v1_core_release_v1 import verify as verify_core_release
from scripts.verify_target_text_corpus_v1_group_split_plan_v1 import verify
from tests import test_verify_target_text_corpus_v1_core_release_v1 as core_helpers


ROOT = Path(__file__).resolve().parents[1]
SPLIT_CONTRACT = ROOT / "configs" / "target_text_corpus_v1_group_split_contract_v1.json"
CORE_CONTRACT = ROOT / "configs" / "target_text_corpus_v1_core_release_contract_v1.json"


class TargetTextCorpusV1GroupSplitPlanTests(unittest.TestCase):
    def make_inputs(self, directory: Path) -> tuple[Path, Path]:
        manifest_path = core_helpers.TargetTextCorpusV1CoreReleaseVerifierTests().make_manifest(directory)
        qa = verify_core_release(CORE_CONTRACT, manifest_path)
        qa_path = directory / "core_release_qa.json"
        qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
        return manifest_path, qa_path

    def test_split_is_exact_metadata_only_and_independently_reproduced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            inputs = self.make_inputs(directory)
            result = build(SPLIT_CONTRACT, *inputs)
            self.assertEqual(result["summary"]["partition_counts"], {"internal_test": 36, "train": 168, "validation": 36})
            self.assertEqual(result["external_holdout_seal"]["record_count"], 60)
            self.assertFalse(result["external_holdout_seal"]["record_ids_exposed"])
            self.assertEqual(result["summary"]["text_fields_exposed"], 0)
            plan_path = directory / "split_plan.json"
            plan_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = verify(plan_path)
            self.assertEqual(qa["status"], "PASS_DETERMINISTIC_SPLIT_REPRODUCED_TRAIN_MATERIALIZATION_RELEASE_REQUIRED")
            self.assertFalse(qa["decision"]["training_allowed_now"])

    def test_same_inputs_produce_identical_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.make_inputs(Path(tmp))
            first = build(SPLIT_CONTRACT, *inputs)
            second = build(SPLIT_CONTRACT, *inputs)
            self.assertEqual(canonical(first), canonical(second))

    def test_partition_assignment_does_not_depend_on_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest_path, qa_path = self.make_inputs(directory)
            first = build(SPLIT_CONTRACT, manifest_path, qa_path)
            changed = json.loads(manifest_path.read_text(encoding="utf-8"))
            text = changed["records"][0]["observed_artifact_visible_text"] + " Independent wording change."
            changed["records"][0]["observed_artifact_visible_text"] = text
            changed["records"][0]["observed_artifact_text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            changed_path = directory / "changed_manifest.json"
            changed_path.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
            changed_qa = verify_core_release(CORE_CONTRACT, changed_path)
            changed_qa_path = directory / "changed_qa.json"
            changed_qa_path.write_text(json.dumps(changed_qa, indent=2) + "\n", encoding="utf-8")
            second = build(SPLIT_CONTRACT, changed_path, changed_qa_path)
            first_map = {row["record_id"]: row["partition"] for row in first["development_assignments"]}
            second_map = {row["record_id"]: row["partition"] for row in second["development_assignments"]}
            self.assertEqual(first_map, second_map)

    def test_stale_release_qa_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest_path, qa_path = self.make_inputs(directory)
            changed = json.loads(manifest_path.read_text(encoding="utf-8"))
            changed["decision"]["training_allowed"] = True
            manifest_path.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build(SPLIT_CONTRACT, manifest_path, qa_path)

    def test_tampered_assignment_fails_independent_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            inputs = self.make_inputs(directory)
            result = build(SPLIT_CONTRACT, *inputs)
            result["development_assignments"][0]["partition"] = "validation"
            plan_path = directory / "tampered_plan.json"
            plan_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = verify(plan_path)
            self.assertEqual(qa["status"], "FAIL")
            self.assertTrue(qa["errors"])


if __name__ == "__main__":
    unittest.main()
