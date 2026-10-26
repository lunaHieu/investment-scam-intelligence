import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_exact_text_release import EXPECTED_IDS, RELEASE_ID
from scripts.extract_sec_edgar_iapd_v11_metadata_recovery_exact_text import execute
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_exact_text_release import QA_ID
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_exact_text_result import PASS_STATUS, verify


class V11MetadataRecoveryExactTextTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, dict]:
        rows = []
        for index, record_id in enumerate(EXPECTED_IDS):
            raw = root / f"{record_id}.html"
            payload = f"<html><head><title>Profile {index}</title></head><body>Independent investment adviser profile with verified archive text {index}.</body></html>".encode()
            raw.write_bytes(payload)
            rows.append({"availability_plan_id": record_id, "shortlist_id": f"SHORT_{index}", "cohort": "EXTERNAL_HOLDOUT", "candidate_host": f"example{index}.invalid", "candidate_url": f"https://example{index}.invalid/", "snapshot_timestamp": "20240101000000", "final_archive_url": f"https://web.archive.org/web/20240101000000id_/https://example{index}.invalid/", "capture_path": str(raw), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "outcome": "CAPTURED"})
        capture = root / "capture.json"
        capture.write_text(json.dumps({"status": "COMPLETE", "results": rows}), encoding="utf-8")
        output_root = root / "exact_text"
        release = {"release_id": RELEASE_ID, "created_at": "2026-10-27T09:00:00+07:00", "inputs": {"capture_report": {"path": str(capture), "sha256": hashlib.sha256(capture.read_bytes()).hexdigest()}}, "outputs": {"text_root": str(output_root / "text"), "manifest": str(output_root / "manifest.jsonl"), "report": str(output_root / "report.json")}, "method": {"minimum_non_whitespace_text_characters": 20}}
        release_path = root / "release.json"
        release_path.write_text(json.dumps(release), encoding="utf-8")
        release_qa = {"verification_id": QA_ID, "status": "PASS_V11_METADATA_RECOVERY_EXACT_TEXT_RELEASE", "inputs": {"release_sha256": hashlib.sha256(release_path.read_bytes()).hexdigest()}, "decision": {"offline_exact_text_extraction_allowed_after_release_qa": True}}
        qa_path = root / "release_qa.json"
        qa_path.write_text(json.dumps(release_qa), encoding="utf-8")
        return release_path, qa_path, release

    def test_offline_extraction_and_independent_byte_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            release_path, qa_path, release = self._fixture(Path(temp))
            report = execute(release_path, qa_path)
            self.assertEqual(report["counts"]["extracted_count"], 2)
            result = verify(release_path, qa_path)
            self.assertEqual(result["status"], PASS_STATUS)
            self.assertEqual(result["checks"]["byte_for_byte_match_count"], 2)
            self.assertFalse(result["decision"]["human_label_review_allowed"])
            self.assertTrue(Path(release["outputs"]["manifest"]).is_file())

    def test_extraction_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            release_path, qa_path, _ = self._fixture(Path(temp))
            execute(release_path, qa_path)
            with self.assertRaises(FileExistsError):
                execute(release_path, qa_path)


if __name__ == "__main__":
    unittest.main()
