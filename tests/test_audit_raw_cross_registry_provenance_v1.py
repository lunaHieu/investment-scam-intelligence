import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_raw_cross_registry_provenance_v1 import (
    build_report,
    iter_hash_pinned_paths,
    should_follow_json_target,
)


class RawCrossRegistryProvenanceV1Tests(unittest.TestCase):
    def test_iter_hash_pinned_paths_pairs_sibling_path_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "artifact.bin"
            target.write_bytes(b"raw")
            digest = hashlib.sha256(b"raw").hexdigest()
            claims = list(iter_hash_pinned_paths({"path": str(target), "sha256": digest}, root))
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0][1], target.resolve())
            self.assertEqual(claims[0][3], digest)

    def test_iter_hash_pinned_paths_does_not_pair_named_hash_to_other_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "data.csv"
            xlsx_path = root / "data.xlsx"
            digest = hashlib.sha256(b"csv").hexdigest()
            claims = list(
                iter_hash_pinned_paths(
                    {"csv_path": str(csv_path), "csv_sha256": digest, "xlsx_companion_path": str(xlsx_path)},
                    root,
                )
            )
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0][1], csv_path.resolve())

    def test_build_report_follows_verified_json_chain_to_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            raw = Path(tmp) / "raw"
            (repo / "configs").mkdir(parents=True)
            (repo / "registry").mkdir()
            raw.mkdir()
            raw_file = raw / "sample.bin"
            raw_file.write_bytes(b"sample")
            raw_hash = hashlib.sha256(raw_file.read_bytes()).hexdigest()
            report_file = Path(tmp) / "capture_report.json"
            report_file.write_text(json.dumps({"path": str(raw_file), "sha256": raw_hash}), encoding="utf-8")
            report_hash = hashlib.sha256(report_file.read_bytes()).hexdigest()
            (repo / "registry" / "root.json").write_text(
                json.dumps({"path": str(report_file), "sha256": report_hash}), encoding="utf-8"
            )

            report = build_report(repo, raw)

            self.assertEqual(report["status"], "PASS_ALL_RAW_HASH_PINNED")
            self.assertEqual(report["summary"]["verified_hash_pinned_chain_files"], 1)
            self.assertEqual(report["summary"]["no_hash_pinned_chain_found_files"], 0)

    def test_json_following_is_limited_to_provenance_artifacts(self) -> None:
        root = Path("D:/raw")
        self.assertTrue(should_follow_json_target(Path("D:/derived/capture_report.json"), root))
        self.assertTrue(should_follow_json_target(Path("D:/raw/source.manifest.json"), root))
        self.assertFalse(should_follow_json_target(Path("D:/derived/model_evaluation_results.json"), root))
        self.assertFalse(should_follow_json_target(Path("D:/curated/validation_split.json"), root))

    def test_build_report_preserves_uncovered_file_without_hashing_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            raw = Path(tmp) / "raw"
            (repo / "configs").mkdir(parents=True)
            (repo / "registry").mkdir()
            raw.mkdir()
            (raw / "uncovered.bin").write_bytes(b"unknown")

            report = build_report(repo, raw)

            self.assertEqual(report["status"], "PASS_PARTIAL_PROVENANCE_GAPS_PRESERVED")
            self.assertEqual(report["summary"]["no_hash_pinned_chain_found_files"], 1)
            self.assertFalse(report["decision"]["complete_raw_provenance_chain_established"])


if __name__ == "__main__":
    unittest.main()
