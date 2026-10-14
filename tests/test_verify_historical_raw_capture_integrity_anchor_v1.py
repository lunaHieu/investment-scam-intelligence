import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_historical_raw_capture_integrity_anchor_v1 import verify


class HistoricalRawCaptureIntegrityAnchorV1Tests(unittest.TestCase):
    def test_exact_matching_evidence_set_passes_without_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "capture_report.json"
            evidence.write_text("{}", encoding="utf-8")
            evidence_hash = hashlib.sha256(evidence.read_bytes()).hexdigest()
            triage = root / "triage.json"
            triage.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "relative_path": "sample.html",
                                "evidence": [
                                    {
                                        "source_document": str(evidence),
                                        "hash_matches": True,
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            anchor = root / "anchor.json"
            anchor.write_text(
                json.dumps(
                    {
                        "inputs": [{"path": str(triage), "sha256": hashlib.sha256(triage.read_bytes()).hexdigest()}],
                        "evidence_documents": [{"path": str(evidence), "sha256": evidence_hash}],
                        "findings": {
                            "anchored_evidence_document_count": 1,
                            "covered_previously_unanchored_raw_files": 1,
                        },
                        "decision": {
                            "files_promoted": 0,
                            "training_allowed": False,
                            "validation_or_test_opening_allowed": False,
                            "labeling_allowed": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(verify(anchor)["covered_previously_unanchored_raw_files"], 1)

    def test_usable_view_cannot_replace_capture_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "usable_capture_view.json"
            evidence.write_text("{}", encoding="utf-8")
            triage = root / "triage.json"
            triage.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "relative_path": "sample.html",
                                "evidence": [{"source_document": str(evidence), "hash_matches": True}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            anchor = root / "anchor.json"
            anchor.write_text(
                json.dumps(
                    {
                        "inputs": [{"path": str(triage), "sha256": hashlib.sha256(triage.read_bytes()).hexdigest()}],
                        "evidence_documents": [],
                        "findings": {
                            "anchored_evidence_document_count": 0,
                            "covered_previously_unanchored_raw_files": 1,
                        },
                        "decision": {
                            "files_promoted": 0,
                            "training_allowed": False,
                            "validation_or_test_opening_allowed": False,
                            "labeling_allowed": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Uncovered triage row"):
                verify(anchor)


if __name__ == "__main__":
    unittest.main()
