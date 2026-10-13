import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.acquire_sec_edgar_submissions_bulk_v1 import safe_zip_summary
from scripts.verify_sec_edgar_submissions_bulk_v1_acquisition import verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class VerifySecEdgarSubmissionsBulkV1AcquisitionTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> Path:
        protocol = root / "protocol.json"
        release = root / "release.json"
        protocol.write_text("{}", encoding="utf-8")
        release.write_text("{}", encoding="utf-8")
        archive = root / "submissions.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("CIK0000000001.json", "{}")
            handle.writestr("README.txt", "metadata")
        summary = safe_zip_summary(archive, full_crc_check=True)
        manifest = {
            "manifest_id": "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1",
            "status": "FROZEN_OFFICIAL_BULK_ARCHIVE_ACQUIRED_NO_CANDIDATES",
            "source_url": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
            "protocol": {"path": str(protocol), "sha256": sha256_file(protocol)},
            "execution_release": {"path": str(release), "sha256": sha256_file(release)},
            "transport": {
                "http_status": 200,
                "request_count": 1,
                "private_identity_runtime_validated": True,
                "private_identity_disclosed": False,
                "private_identity_hash_disclosed": False,
            },
            "raw_artifact": {
                "path": str(archive),
                "bytes": archive.stat().st_size,
                "sha256": sha256_file(archive),
                **summary,
            },
            "interpretation": {
                "public_filing_history_reference_only": True,
                "automatic_legitimate_label": False,
                "candidate_enumeration_allowed": False,
                "independent_identity_review_required": True,
            },
            "safety_contract": {
                "candidate_domain_access_operations": 0,
                "candidate_records_enumerated": 0,
                "artifact_captures": 0,
                "labels_created": 0,
                "model_operations": 0,
                "training_allowed": False,
            },
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest_path

    def test_verifies_hash_size_zip_privacy_and_closed_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = verify(self.make_fixture(root), root, full_crc_check=True)
            self.assertEqual(result["status"], "VERIFIED_IMMUTABLE_RAW_REFERENCE_ONLY")
            self.assertEqual(result["non_json_member_count"], 1)
            self.assertFalse(result["training_allowed"])

    def test_rejects_archive_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = self.make_fixture(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            archive = Path(manifest["raw_artifact"]["path"])
            with archive.open("ab") as handle:
                handle.write(b"tamper")
            with self.assertRaisesRegex(ValueError, "byte size"):
                verify(manifest_path, root, full_crc_check=False)


if __name__ == "__main__":
    unittest.main()
