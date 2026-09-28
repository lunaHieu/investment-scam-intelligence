import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_external_text_intake import sha256_bytes, sha256_file, validate_batch


def make_record(
    capture_path,
    capture_hash,
    *,
    suffix="A",
    status="CONFIRMED",
    text="Guaranteed weekly returns are available when you deposit today.",
    near_group=None,
):
    support = "SCAM_CLAIM" if status == "CONFIRMED" else "LEGITIMACY"
    evidence_type = "enforcement_record" if status == "CONFIRMED" else "official_registry"
    return {
        "case_id": f"CASE_{suffix}",
        "ground_truth_status": status,
        "label_confidence": "HIGH",
        "review_status": "RECONCILED",
        "review_rationale": "Evidence and the observed artifact were reviewed independently.",
        "case_or_campaign_group_id": f"CASEGRP_{suffix}",
        "near_duplicate_group_id": near_group or f"NDG_{suffix}",
        "artifact": {
            "artifact_id": f"ART_{suffix}",
            "source_id": "external_manual_capture",
            "source_record_id": f"SRC_{suffix}",
            "artifact_type": "WEBSITE_SNAPSHOT",
            "text": text,
            "text_sha256": sha256_bytes(text.encode("utf-8")),
            "language": "en",
            "url": f"https://example.test/{suffix.lower()}",
            "collection_date": "2026-09-23",
            "content_observed_at": "2026-09-23T00:00:00+00:00",
            "source_capture_path": capture_path,
            "source_capture_sha256": capture_hash,
        },
        "evidence": [
            {
                "evidence_id": f"EVD_{suffix}",
                "evidence_type": evidence_type,
                "source_id": "official_evidence",
                "source_url": f"https://regulator.example/{suffix.lower()}",
                "summary": "Independent reviewed evidence for the bounded case.",
                "supports": [support],
                "reviewed": True,
            }
        ],
    }


def make_batch(records, status="RECONCILED"):
    return {
        "batch_id": "EXTERNAL_TEXT_PILOT_TEST",
        "status": status,
        "policy_id": "ISI_TEXT_BASELINE_V2_EXTERNAL_EVAL_POLICY_V1",
        "created_at": "2026-09-23T00:00:00+00:00",
        "source_scope": ["external_manual_capture"],
        "records": records,
    }


class ExternalTextIntakeTests(unittest.TestCase):
    def test_empty_template_is_structurally_valid_but_not_reporting_ready(self):
        template = json.loads(
            (
                ROOT
                / "registry"
                / "pilots"
                / "external_text_evaluation_intake_template.json"
            ).read_text(encoding="utf-8")
        )
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            errors, report = validate_batch(template, Path(temp_dir))
        self.assertEqual(errors, [])
        self.assertEqual(report["eligible_count"], 0)
        self.assertFalse(report["reporting_allowed"])

    def test_reconciled_confirmed_record_with_capture_is_eligible(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            root = Path(temp_dir)
            capture = root / "source" / "capture.html"
            capture.parent.mkdir(parents=True)
            capture.write_text("<html>captured source</html>", encoding="utf-8")
            record = make_record("source/capture.html", sha256_file(capture))
            errors, report = validate_batch(make_batch([record]), root)
        self.assertEqual(errors, [])
        self.assertEqual(report["eligible_count"], 1)
        self.assertEqual(report["eligible_confirmed"], 1)
        self.assertFalse(report["reporting_allowed"])

    def test_complaint_cannot_be_model_input_artifact(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            root = Path(temp_dir)
            capture = root / "capture.json"
            capture.write_text("{}", encoding="utf-8")
            record = make_record("capture.json", sha256_file(capture))
            record["artifact"]["artifact_type"] = "COMPLAINT"
            errors, report = validate_batch(make_batch([record]), root)
        self.assertTrue(any("artifact_type is not allowed" in error for error in errors))
        self.assertFalse(report["record_results"][0]["eligible"])

    def test_exact_duplicate_text_must_share_near_duplicate_group(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            root = Path(temp_dir)
            capture = root / "capture.txt"
            capture.write_text("captured", encoding="utf-8")
            capture_hash = sha256_file(capture)
            first = make_record("capture.txt", capture_hash, suffix="A", near_group="NDG_A")
            second = make_record("capture.txt", capture_hash, suffix="B", near_group="NDG_B")
            errors, _ = validate_batch(make_batch([first, second]), root)
        self.assertTrue(any("spans multiple near_duplicate_group_id" in error for error in errors))

    def test_conflicting_labels_cannot_share_case_group(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            root = Path(temp_dir)
            capture = root / "capture.txt"
            capture.write_text("captured", encoding="utf-8")
            capture_hash = sha256_file(capture)
            first = make_record("capture.txt", capture_hash, suffix="A", near_group="NDG_A")
            second = make_record(
                "capture.txt",
                capture_hash,
                suffix="B",
                status="LEGITIMATE",
                text="This is an independently observed legitimate investment page.",
                near_group="NDG_B",
            )
            second["case_or_campaign_group_id"] = first["case_or_campaign_group_id"]
            errors, _ = validate_batch(make_batch([first, second]), root)
        self.assertTrue(any("conflicting eligible labels" in error for error in errors))

    def test_uncertain_record_does_not_imply_legitimacy_evidence_requirement(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            root = Path(temp_dir)
            capture = root / "capture.txt"
            capture.write_text("captured", encoding="utf-8")
            record = make_record("capture.txt", sha256_file(capture), status="UNCERTAIN")
            record["label_confidence"] = "LOW"
            record["review_status"] = "IN_REVIEW"
            errors, report = validate_batch(make_batch([record], status="IN_REVIEW"), root)
        self.assertEqual(errors, [])
        reasons = report["record_results"][0]["eligibility_reasons"]
        self.assertIn("ground_truth_status_not_confirmed_or_legitimate", reasons)
        self.assertNotIn("no_reviewed_legitimacy_evidence", reasons)


if __name__ == "__main__":
    unittest.main()
