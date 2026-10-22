import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_channel_contribution_v1 import build
from scripts.verify_target_text_corpus_v1_channel_contribution_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "target_text_corpus_v1_core_release_contract_v1.json"
MATRIX = ROOT / "configs" / "target_text_corpus_v1_sampling_matrix_v1.json"
CHANNEL = "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE"


class TargetTextCorpusV1ChannelContributionV1Tests(unittest.TestCase):
    def manifest(self, path: Path, count: int = 75) -> Path:
        matrix_hash = hashlib.sha256(MATRIX.read_bytes()).hexdigest()
        records = []
        for index in range(count):
            cohort = "DEVELOPMENT" if index < min(60, count) else "EXTERNAL_HOLDOUT"
            text = f"Unique visible investment advisory artifact number {index}."
            language = "vi" if (cohort == "DEVELOPMENT" and index < 12) or (cohort == "EXTERNAL_HOLDOUT" and index < 63) else "en"
            records.append({
                "record_id": f"record-{index:03d}", "target_status": "LEGITIMATE", "channel_id": CHANNEL, "cohort": cohort,
                "fresh_cohort": True, "human_reviewed_language": True, "opened_cohort_exclusion_pass": True, "cross_partition_exclusion_pass": True,
                "evidence_confidence": "HIGH", "review_status": "RECONCILED_OWNER_ACCEPTED",
                "observed_artifact_visible_text": text, "observed_artifact_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "raw_capture_sha256": hashlib.sha256(f"raw-{index}".encode()).hexdigest(),
                "primary_review_sha256": "1" * 64, "blind_second_review_sha256": "2" * 64, "reconciliation_sha256": "3" * 64,
                "owner_acceptance_sha256": "4" * 64, "channel_contribution_qa_sha256": "5" * 64,
                "source_url": f"https://web.archive.org/web/2026010100{index:04d}id_/https://example-{index}.test/",
                "collected_at": "2026-10-22T12:00:00+07:00", "language_code": language,
                "transitive_group_id": f"t-{index}", "case_campaign_group_id": f"c-{index}", "entity_domain_family_group_id": f"e-{index}", "near_duplicate_group_id": f"n-{index}",
                "release_eligibility": "NO_PENDING_GROUP_SPLIT_RELEASE" if cohort == "DEVELOPMENT" else "NO_EXTERNAL_HOLDOUT",
                "model_scoring_eligibility": "NO" if cohort == "DEVELOPMENT" else "NO_PENDING_FROZEN_EVALUATION_RELEASE",
            })
        manifest = {"status": "FROZEN_OWNER_ACCEPTED_CHANNEL_CANDIDATES", "channel_id": CHANNEL, "sampling_matrix_sha256": matrix_hash, "records": records}
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return path

    def test_builds_and_independently_reproduces_exact_channel_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest = self.manifest(directory / "manifest.json")
            result = build(CONTRACT, MATRIX, manifest, CHANNEL)
            self.assertEqual(result["counts"], {"DEVELOPMENT": 60, "EXTERNAL_HOLDOUT": 15, "total": 75})
            contribution = directory / "contribution.json"
            contribution.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            qa = verify(contribution, CONTRACT, MATRIX, manifest, CHANNEL)
            self.assertEqual(qa["status"], "PASS_CHANNEL_CONTRIBUTION_INDEPENDENTLY_REPRODUCED")
            self.assertFalse(qa["decision"]["training_allowed"])

    def test_rejects_partial_realistic_population(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.manifest(Path(tmp) / "manifest.json", count=42)
            with self.assertRaisesRegex(ValueError, "Channel quota mismatch"):
                build(CONTRACT, MATRIX, manifest, CHANNEL)

    def test_rejects_missing_human_language_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.manifest(Path(tmp) / "manifest.json")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["records"][0]["human_reviewed_language"] = False
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "human_reviewed_language"):
                build(CONTRACT, MATRIX, manifest, CHANNEL)


if __name__ == "__main__":
    unittest.main()
