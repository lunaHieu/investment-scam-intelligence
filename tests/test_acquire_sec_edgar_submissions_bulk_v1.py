import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.acquire_sec_edgar_submissions_bulk_v1 import (
    acquire,
    public_manifest,
    safe_zip_summary,
    validate_execution_release,
    validate_private_identity,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_source_capacity_amendment_protocol_v1.json"
TOOLING_REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_submissions_bulk_v1_tooling.json"
FROZEN_OUTPUT = Path(r"D:\nckh 2026-2027\ISI_Data\raw\sec_edgar_bulk\submissions_2026-10-12.zip")
FROZEN_MANIFEST = FROZEN_OUTPUT.with_suffix(".manifest.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AcquireSecEdgarSubmissionsBulkV1Tests(unittest.TestCase):
    def test_private_identity_is_validated_without_entering_public_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = root / "private.json"
            identity.write_text(
                json.dumps(
                    {
                        "organization_or_project": "Academic Project",
                        "contact_email": "researcher@example.org",
                        "purpose": "Investment scam intelligence research",
                    }
                ),
                encoding="utf-8",
            )
            release_path = root / "release.json"
            release_path.write_text("{}", encoding="utf-8")
            user_agent = validate_private_identity(identity)
            manifest = public_manifest(
                protocol_path=PROTOCOL,
                release_path=release_path,
                source_url="https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
                output_path=root / "submissions.zip",
                collected_at="2026-10-12T00:00:00+00:00",
                status_code=200,
                content_type="application/zip",
                bytes_written=123,
                archive_sha256="a" * 64,
                zip_summary={
                    "member_count": 1,
                    "json_member_count": 1,
                    "uncompressed_bytes": 2,
                    "compressed_bytes": 2,
                },
            )
            serialized = json.dumps(manifest)
            self.assertIn("Academic Project", user_agent)
            self.assertNotIn("researcher@example.org", serialized)
            self.assertNotIn(str(identity), serialized)

    def test_zip_summary_records_mixed_extensions_and_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            safe = root / "safe.zip"
            with zipfile.ZipFile(safe, "w") as archive:
                archive.writestr("CIK0000000001.json", "{}")
                archive.writestr("README.txt", "metadata")
            summary = safe_zip_summary(safe, full_crc_check=True)
            self.assertEqual(summary["json_member_count"], 1)
            self.assertEqual(summary["non_json_member_count"], 1)
            self.assertEqual(summary["file_extension_counts"], {".json": 1, ".txt": 1})

            unsafe = root / "unsafe.zip"
            with zipfile.ZipFile(unsafe, "w") as archive:
                archive.writestr("../escape.json", "{}")
            with self.assertRaisesRegex(ValueError, "unsafe member path"):
                safe_zip_summary(unsafe, full_crc_check=False)

    def test_network_execution_requires_a_valid_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, "release"):
                validate_execution_release(
                    root / "release.json",
                    PROTOCOL,
                    TOOLING_REGISTRY,
                    FROZEN_OUTPUT,
                    FROZEN_MANIFEST,
                )

    def test_release_cannot_open_candidate_or_model_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release_path = root / "release.json"
            output = root / "submissions.zip"
            manifest = root / "submissions.manifest.json"
            release_path.write_text(
                json.dumps(
                    {
                        "release_id": "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1_EXECUTION_RELEASE",
                        "status": "FROZEN_ONE_SHOT_NETWORK_EXECUTION_RELEASED",
                        "basis": [
                            {
                                "role": "source_capacity_amendment_protocol",
                                "path": str(PROTOCOL),
                                "sha256": sha256_file(PROTOCOL),
                            },
                            {
                                "role": "sec_bulk_tooling_registry",
                                "path": str(TOOLING_REGISTRY),
                                "sha256": sha256_file(TOOLING_REGISTRY),
                            },
                        ],
                        "execution_scope": {
                            "source_url": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
                            "maximum_requests": 1,
                            "raw_output": str(output),
                            "manifest_output": str(manifest),
                        },
                        "private_identity_evidence": {
                            "file_exists_at_release": True,
                            "required_fields_validated_at_release": True,
                            "contents_disclosed": False,
                            "hash_disclosed": False,
                            "runtime_revalidation_required": True,
                        },
                        "decision": {
                            "sec_bulk_network_execution_allowed": True,
                            "candidate_enumeration_allowed": True,
                            "capture_allowed": False,
                            "labeling_allowed": False,
                            "training_allowed": False,
                            "model_scoring_allowed": False,
                            "validation_or_test_opening_allowed": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PermissionError, "decision contract changed"):
                validate_execution_release(
                    release_path,
                    PROTOCOL,
                    TOOLING_REGISTRY,
                    output,
                    manifest,
                )

    def test_registered_tooling_hashes_are_current_and_execution_closed(self) -> None:
        registry_path = (
            ROOT / "registry" / "analyses" / "sec_edgar_submissions_bulk_v1_tooling.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertTrue(registry["decision"]["tooling_ready"])
        self.assertTrue(registry["decision"]["network_execution_allowed_only_with_release"])
        self.assertFalse(registry["decision"]["training_allowed"])
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
