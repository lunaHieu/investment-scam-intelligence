import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_target_text_corpus_v1_exact_text import execute, prepare_extraction
from scripts.verify_target_text_corpus_v1_exact_text import verify


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TargetTextCorpusExactTextTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> Path:
        repo = root / "repo"
        (repo / "configs").mkdir(parents=True)
        (repo / "registry" / "analyses").mkdir(parents=True)
        data = root / "data"
        data.mkdir()
        protocol = repo / "configs" / "protocol.json"
        protocol.write_text("{}\n", encoding="utf-8")
        registry = repo / "registry" / "analyses" / "capture.json"
        registry.write_text(json.dumps({"decision": {
            "exact_text_extraction_allowed_for_captured_rows": True,
            "binary_labeling_allowed": False,
        }}) + "\n", encoding="utf-8")
        queue = data / "queue.jsonl"
        queue.write_text(json.dumps({
            "candidate_id": "TTCV1_CAND_TEST_001",
            "channel_id": "TEST_CHANNEL",
            "channel_target_stratum": "CONFIRMED",
            "reference": {"source_id": "test", "source_record_id": "1", "source_url": "https://reference.invalid/1"},
        }) + "\n", encoding="utf-8")
        raw = data / "capture.html.gz"
        raw.write_bytes(gzip.compress(b"<html><head><link rel='canonical' href='https://example.invalid/'></head><body>Hello <script>hidden</script>investment world</body></html>"))
        report = data / "capture-report.json"
        report.write_text(json.dumps({
            "report_id": "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_REPORT_V2",
            "results": [{
                "candidate_id": "TTCV1_CAND_TEST_001", "channel_id": "TEST_CHANNEL",
                "channel_target_stratum": "CONFIRMED", "candidate_host": "example.invalid",
                "snapshot_timestamp": "20260101000000", "requested_archive_url": "https://web.archive.org/web/20260101000000id_/https://example.invalid/",
                "final_archive_url": "https://web.archive.org/web/20260101000000id_/https://example.invalid/",
                "capture_path": str(raw), "outcome": "CAPTURED", "bytes": raw.stat().st_size, "sha256": sha(raw),
            }],
        }) + "\n", encoding="utf-8")
        qa = data / "qa.json"
        qa.write_text(json.dumps({"status": "PASS_23_RAW_CAPTURES_6_SMALL_RESPONSES_PRESERVED"}) + "\n", encoding="utf-8")
        out = data / "out"
        inputs = {
            "protocol": protocol, "capture_result_registry": registry,
            "candidate_queue": queue, "capture_report": report, "capture_independent_qa": qa,
        }
        config = repo / "configs" / "extract.json"
        config.write_text(json.dumps({
            "extraction_id": "ISI_TARGET_TEXT_CORPUS_V1_EXACT_TEXT_EXTRACTION_V1",
            "inputs": {key: {"path": str(path), "sha256": sha(path)} for key, path in inputs.items()},
            "expected_input": {"captured_count": 1, "failed_count_preserved": 0, "captured_by_channel": {"TEST_CHANNEL": 1}},
            "method": {"minimum_non_whitespace_text_characters": 20},
            "outputs": {"text_root": str(out / "text"), "manifest": str(out / "manifest.jsonl"), "report": str(out / "report.json")},
            "safety_contract": {"network_operations": 0, "live_domain_access_allowed": False, "raw_files_modified": False, "labels_created": 0, "labels_changed": 0, "model_fit_operations": 0, "model_scoring_operations": 0, "validation_or_test_openings": 0, "training_allowed": False},
        }) + "\n", encoding="utf-8")
        return config

    def test_extracts_gzip_visible_text_and_independent_verifier_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_fixture(Path(directory))
            report = execute(config)
            self.assertEqual(report["counts"]["extracted_count"], 1)
            output = Path(json.loads(config.read_text())["outputs"]["text_root"]) / "TTCV1_CAND_TEST_001.txt"
            self.assertEqual(output.read_text(encoding="utf-8"), "Hello investment world")
            result = verify(config)
            self.assertFalse(result["errors"], result["errors"])
            self.assertEqual(result["checks"]["byte_for_byte_match_count"], 1)

    def test_raw_hash_mismatch_is_rejected_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_fixture(Path(directory))
            value = json.loads(config.read_text(encoding="utf-8"))
            capture_report = Path(value["inputs"]["capture_report"]["path"])
            report = json.loads(capture_report.read_text(encoding="utf-8"))
            report["results"][0]["sha256"] = "0" * 64
            capture_report.write_text(json.dumps(report) + "\n", encoding="utf-8")
            value["inputs"]["capture_report"]["sha256"] = sha(capture_report)
            config.write_text(json.dumps(value) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Raw capture byte/hash mismatch"):
                prepare_extraction(config)
            self.assertFalse(Path(value["outputs"]["text_root"]).exists())

    def test_refuses_to_overwrite_frozen_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_fixture(Path(directory))
            execute(config)
            with self.assertRaises(FileExistsError):
                execute(config)


if __name__ == "__main__":
    unittest.main()
