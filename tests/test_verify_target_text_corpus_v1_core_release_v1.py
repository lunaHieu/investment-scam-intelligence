import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_core_release_v1 import sha256_file, verify


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "target_text_corpus_v1_core_release_contract_v1.json"
MATRIX = ROOT / "configs" / "target_text_corpus_v1_sampling_matrix_v1.json"


class TargetTextCorpusV1CoreReleaseVerifierTests(unittest.TestCase):
    def make_manifest(self, directory: Path) -> Path:
        matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        records = []
        descriptors = []
        channel_ids: dict[str, list[str]] = {}
        for channel in matrix["channel_quotas"]:
            channel_id = channel["channel_id"]
            target_status = channel["target_status"]
            ids = []
            for cohort, count in (
                ("DEVELOPMENT", channel["development_accepted_group_quota"]),
                ("EXTERNAL_HOLDOUT", channel["external_holdout_accepted_group_quota"]),
            ):
                for index in range(count):
                    record_id = f"{channel_id.lower()}-{cohort.lower()}-{index:03d}"
                    ids.append(record_id)
                    if cohort == "DEVELOPMENT":
                        language = "vi" if index < 3 else ("es" if index < 6 else "en")
                    else:
                        language = "vi" if index < 1 else ("es" if index < 2 else "en")
                    text = f"Archived investment-related visible text for frozen record {record_id}."
                    records.append({
                        "record_id": record_id,
                        "target_status": target_status,
                        "channel_id": channel_id,
                        "cohort": cohort,
                        "transitive_group_id": f"transitive-{record_id}",
                        "case_campaign_group_id": f"case-{record_id}",
                        "entity_domain_family_group_id": f"entity-{record_id}",
                        "near_duplicate_group_id": f"near-{record_id}",
                        "observed_artifact_visible_text": text,
                        "observed_artifact_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "raw_capture_sha256": hashlib.sha256(f"capture-{record_id}".encode()).hexdigest(),
                        "source_url": f"https://web.archive.org/web/20261001000000id_/https://{record_id}.example.invalid/",
                        "collected_at": "2026-10-14T23:25:00+07:00",
                        "language_code": language,
                        "human_reviewed_language": True,
                        "fresh_cohort": True,
                        "opened_cohort_exclusion_pass": True,
                        "cross_partition_exclusion_pass": True,
                        "evidence_confidence": "HIGH",
                        "review_status": "RECONCILED_OWNER_ACCEPTED",
                        "primary_review_sha256": hashlib.sha256(f"primary-{record_id}".encode()).hexdigest(),
                        "blind_second_review_sha256": hashlib.sha256(f"second-{record_id}".encode()).hexdigest(),
                        "reconciliation_sha256": hashlib.sha256(f"reconciliation-{record_id}".encode()).hexdigest(),
                        "owner_acceptance_sha256": hashlib.sha256(f"acceptance-{record_id}".encode()).hexdigest(),
                        "channel_contribution_qa_sha256": "PENDING",
                        "release_eligibility": "NO_PENDING_GROUP_SPLIT_RELEASE" if cohort == "DEVELOPMENT" else "NO_EXTERNAL_HOLDOUT",
                        "model_scoring_eligibility": "NO" if cohort == "DEVELOPMENT" else "NO_PENDING_FROZEN_EVALUATION_RELEASE",
                    })
            channel_ids[channel_id] = ids

        for channel_id, ids in channel_ids.items():
            contribution = {
                "status": "PASS_CHANNEL_CONTRIBUTION_READY",
                "channel_id": channel_id,
                "record_ids": ids,
                "decision": {"dataset_release_contribution_allowed": True, "training_allowed": False},
            }
            path = directory / f"{channel_id.lower()}_contribution.json"
            path.write_text(json.dumps(contribution, indent=2) + "\n", encoding="utf-8")
            digest = sha256_file(path)
            descriptors.append({"channel_id": channel_id, "path": path.name, "sha256": digest})
            for row in records:
                if row["channel_id"] == channel_id:
                    row["channel_contribution_qa_sha256"] = digest

        manifest = {
            "release_id": "ISI_TARGET_TEXT_CORPUS_V1_CORE_RELEASE_V1",
            "status": "PROPOSED_BALANCED_RELEASE_INDEPENDENT_QA_REQUIRED",
            "sampling_matrix_sha256": sha256_file(MATRIX),
            "channel_contributions": descriptors,
            "records": records,
            "decision": {
                "independent_qa_passed": False,
                "development_group_split_plan_allowed": False,
                "training_allowed": False,
                "validation_or_test_opening_allowed": False,
                "external_holdout_model_scoring_allowed": False,
            },
        }
        manifest_path = directory / "core_release_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest_path

    def mutate(self, source: Path, directory: Path, callback) -> Path:
        value = json.loads(source.read_text(encoding="utf-8"))
        changed = copy.deepcopy(value)
        callback(changed)
        path = directory / "mutated_manifest.json"
        path.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
        return path

    def test_balanced_grouped_release_passes_without_opening_model_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_manifest(Path(tmp))
            result = verify(CONTRACT, path)
            self.assertEqual(result["status"], "PASS_BALANCED_GROUPED_RELEASE_PARTITION_PLAN_REQUIRED")
            self.assertEqual(result["checks"]["record_count"], 300)
            self.assertEqual(result["checks"]["development_groups"], 240)
            self.assertEqual(result["checks"]["external_holdout_groups"], 60)
            self.assertFalse(result["decision"]["training_allowed_now"])
            self.assertFalse(result["decision"]["external_holdout_model_scoring_allowed"])

    def test_cross_cohort_group_collision_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self.make_manifest(directory)
            def change(value):
                development = next(row for row in value["records"] if row["cohort"] == "DEVELOPMENT")
                holdout = next(row for row in value["records"] if row["cohort"] == "EXTERNAL_HOLDOUT")
                holdout["transitive_group_id"] = development["transitive_group_id"]
            path = self.mutate(source, directory, change)
            with self.assertRaisesRegex(ValueError, "overlapping transitive_group_id"):
                verify(CONTRACT, path)

    def test_language_shortfall_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self.make_manifest(directory)
            path = self.mutate(source, directory, lambda value: [row.update({"language_code": "en-US"}) for row in value["records"]])
            with self.assertRaisesRegex(ValueError, "Non-English quota not met"):
                verify(CONTRACT, path)

    def test_external_holdout_cannot_be_opened_for_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self.make_manifest(directory)
            def change(value):
                row = next(item for item in value["records"] if item["cohort"] == "EXTERNAL_HOLDOUT")
                row["model_scoring_eligibility"] = "YES"
            path = self.mutate(source, directory, change)
            with self.assertRaisesRegex(ValueError, "Model-scoring eligibility mismatch"):
                verify(CONTRACT, path)

    def test_partition_cannot_be_assigned_before_group_split_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self.make_manifest(directory)
            path = self.mutate(source, directory, lambda value: value["records"][0].update({"partition": "train"}))
            with self.assertRaisesRegex(ValueError, "Forbidden pre-release field partition"):
                verify(CONTRACT, path)

    def test_non_raw_wayback_replay_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self.make_manifest(directory)
            def change(value):
                value["records"][0]["source_url"] = value["records"][0]["source_url"].replace("id_/", "/")
            path = self.mutate(source, directory, change)
            with self.assertRaisesRegex(ValueError, "not a raw Wayback replay"):
                verify(CONTRACT, path)

    def test_exact_text_collision_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self.make_manifest(directory)
            def change(value):
                value["records"][1]["observed_artifact_visible_text"] = value["records"][0]["observed_artifact_visible_text"]
                value["records"][1]["observed_artifact_text_sha256"] = value["records"][0]["observed_artifact_text_sha256"]
            path = self.mutate(source, directory, change)
            with self.assertRaisesRegex(ValueError, "Exact text collision"):
                verify(CONTRACT, path)


if __name__ == "__main__":
    unittest.main()
