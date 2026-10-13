import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_sec_edgar_all_filer_identity_index_v1 import build
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


class BuildSecEdgarAllFilerIdentityIndexV1Tests(unittest.TestCase):
    def make_config(self, root: Path) -> Path:
        basis_a = root / "basis-a.json"
        basis_b = root / "basis-b.json"
        basis_a.write_text("{}", encoding="utf-8")
        basis_b.write_text("{}", encoding="utf-8")
        raw = root / "submissions.zip"
        with zipfile.ZipFile(raw, "w") as archive:
            archive.writestr("CIK0000000001.json", json.dumps({"cik": "1", "name": "Alpha LLC"}))
            archive.writestr(
                "CIK0000000001-submissions-001.json", json.dumps({"accessionNumber": []})
            )
            archive.writestr("CIK0000000002.json", json.dumps({"cik": "2", "name": ""}))
            archive.writestr("README.txt", "metadata")
        manifest = root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        output = root / "identity-index-v1"
        config = {
            "amendment_id": "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1_STORAGE_AMENDMENT_V1",
            "status": "FROZEN_LOGICAL_JSON_EXTRACTION_APPROVED_LOOSE_FILE_EXPANSION_BLOCKED",
            "basis": [
                {"role": "a", "path": str(basis_a), "sha256": sha256_file(basis_a)},
                {"role": "b", "path": str(basis_b), "sha256": sha256_file(basis_b)},
            ],
            "raw_input": {
                "path": str(raw),
                "sha256": sha256_file(raw),
                "manifest_path": str(manifest),
                "manifest_sha256": sha256_file(manifest),
            },
            "preflight": {
                "member_count": 4,
                "primary_submission_json_members": 2,
                "historical_submission_json_members": 1,
                "non_json_members": 1,
                "empty_name_primary_members": 1,
            },
            "logical_extraction": {
                "output_directory": str(output),
                "index_filename": "identity_index.jsonl",
                "report_filename": "report.json",
                "expected_output_records": 1,
            },
            "decision": {
                "logical_extraction_execution_allowed": True,
                "candidate_enumeration_allowed": False,
                "shortlist_materialization_allowed": False,
                "labeling_allowed": False,
                "validation_or_test_opening_allowed": False,
                "training_allowed": False,
            },
        }
        path = root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_builds_compact_index_and_excludes_history_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = build(self.make_config(root))
            output = Path(result["output_directory"])
            rows = [json.loads(line) for line in (output / "identity_index.jsonl").read_text().splitlines()]
            self.assertEqual(rows, [{"cik": "0000000001", "name": "Alpha LLC"}])
            self.assertEqual(result["scope"]["excluded_historical_submission_members"], 1)
            self.assertEqual(result["scope"]["excluded_non_json_members"], 1)
            self.assertEqual(result["scope"]["excluded_empty_name_primary_members"], 1)
            self.assertFalse(result["safety_contract"]["training_allowed"])

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.make_config(root)
            build(config)
            with self.assertRaisesRegex(FileExistsError, "overwrite"):
                build(config)


if __name__ == "__main__":
    unittest.main()
