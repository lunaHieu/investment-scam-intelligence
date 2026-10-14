import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.triage_unanchored_raw_provenance_v1 import build_report, evidence_documents


class UnanchoredRawProvenanceTriageV1Tests(unittest.TestCase):
    def test_evidence_discovery_is_filename_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            derived = root / "derived" / "branch"
            curated = root / "curated" / "branch"
            derived.mkdir(parents=True)
            curated.mkdir(parents=True)
            (derived / "capture_report.json").write_text("{}", encoding="utf-8")
            (curated / "model_evaluation.json").write_text("{}", encoding="utf-8")
            self.assertEqual([path.name for path in evidence_documents(root)], ["capture_report.json"])

    def test_matching_unanchored_evidence_is_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            raw.mkdir()
            target = raw / "sample.html"
            target.write_bytes(b"capture")
            target_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            audit = root / "prior.json"
            audit.write_text(
                json.dumps(
                    {
                        "raw_inventory": [
                            {"relative_path": "sample.html", "category": "NO_HASH_PINNED_CHAIN_FOUND"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            audit_hash = hashlib.sha256(audit.read_bytes()).hexdigest()
            evidence_dir = root / "derived" / "captures"
            evidence_dir.mkdir(parents=True)
            (root / "curated").mkdir()
            (evidence_dir / "capture_report.json").write_text(
                json.dumps({"path": str(target), "sha256": target_hash}), encoding="utf-8"
            )

            report = build_report(audit, audit_hash, root, raw)

            self.assertEqual(report["summary"]["matching_unanchored_hash_evidence_files"], 1)
            self.assertEqual(report["decision"]["files_promoted"], 0)
            self.assertFalse(report["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
