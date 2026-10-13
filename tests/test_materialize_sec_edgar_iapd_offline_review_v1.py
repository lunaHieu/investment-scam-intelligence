import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.materialize_sec_edgar_iapd_offline_review_v1 import classify_name_evidence, materialize
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class MaterializeSecEdgarIapdOfflineReviewV1Tests(unittest.TestCase):
    def test_name_review_is_conservative(self) -> None:
        exact = classify_name_evidence("Alpha Advisors, LLC", "the alpha advisors llc", 0.8)
        compatible = classify_name_evidence("North Point Portfolio Managers Corp/OH", "North Point Portfolio Managers Corporation", 0.8)
        caution = classify_name_evidence("1248 Management LLC", "1248 Partners LLC", 0.8)
        self.assertEqual(exact["identity_review_status"], "OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS")
        self.assertEqual(compatible["identity_review_status"], "OFFLINE_COMPATIBLE_NAME_VARIANT_EVIDENCE_PASS")
        self.assertEqual(caution["future_capture_planning_recommendation"], "HOLD_FOR_DEEPER_IDENTITY_REVIEW")

    def test_materializes_only_shortlisted_member_and_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            basis = root / "basis.json"
            basis.write_text("{}", encoding="utf-8")
            archive = root / "submissions.zip"
            raw_selected = json.dumps({"cik": "1", "name": "Alpha Advisors LLC", "filings": {"recent": {}}}).encode()
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("CIK0000000001.json", raw_selected)
                handle.writestr("CIK0000000002.json", json.dumps({"cik": "2", "name": "Other LLC"}))
            host = "alpha.test"
            import hashlib
            host_hash = hashlib.sha256(host.encode()).hexdigest()
            shortlist = root / "shortlist.jsonl"
            shortlist.write_text(json.dumps({
                "shortlist_id": "DEV_001", "cohort": "DEVELOPMENT", "cik": "0000000001",
                "edgar_entity_name": "Alpha Advisors LLC", "iapd_source_record_id": "10",
                "iapd_entity_name": "alpha advisors llc", "normalized_host": host,
                "normalized_host_sha256": host_hash, "candidate_live_domain_accessed": False,
                "wayback_queried": False, "artifact_captured": False, "label_created": False,
                "ground_truth_status": "UNCERTAIN", "training_eligible": "NO"
            }) + "\n", encoding="utf-8")
            iapd = root / "iapd.jsonl"
            iapd.write_text(json.dumps({"source_record_id": "10", "entity_name_from_reference": "alpha advisors llc", "normalized_host": host, "candidate_url": "https://alpha.test/"}) + "\n", encoding="utf-8")
            output = root / "output"
            config = {
                "protocol_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_OFFLINE_REVIEW_V1",
                "basis": [{"role": "basis", "path": str(basis), "sha256": sha256_file(basis)}],
                "inputs": {
                    "raw_archive": {"path": str(archive), "sha256": sha256_file(archive)},
                    "shortlist": {"path": str(shortlist), "sha256": sha256_file(shortlist), "record_count": 1},
                    "iapd_normalized": {"path": str(iapd), "sha256": sha256_file(iapd), "record_count": 1},
                },
                "review_contract": {"compatible_full_token_jaccard_minimum": 0.8},
                "outputs": {"directory": str(output), "evidence_subdirectory": "submission_records", "review_records_filename": "reviews.jsonl", "report_filename": "report.json"},
                "decision": {
                    "shortlist_only_evidence_extraction_allowed": True, "offline_provenance_review_allowed": True,
                    "candidate_live_domain_access_allowed": False, "wayback_query_allowed": False,
                    "artifact_capture_allowed": False, "labeling_allowed": False,
                    "validation_or_test_opening_allowed": False, "training_allowed": False,
                },
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            result = materialize(config_path)
            self.assertEqual((output / "submission_records" / "CIK0000000001.json").read_bytes(), raw_selected)
            self.assertFalse((output / "submission_records" / "CIK0000000002.json").exists())
            self.assertEqual(result["output"]["evidence_record_count"], 1)
            self.assertEqual(result["safety_contract"]["network_operations"], 0)
            with self.assertRaisesRegex(FileExistsError, "overwrite"):
                materialize(config_path)


if __name__ == "__main__":
    unittest.main()
