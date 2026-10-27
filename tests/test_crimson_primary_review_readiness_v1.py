import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_crimson_primary_review_readiness_v1 import PASS_STATUS, audit, write_report
from scripts.verify_crimson_primary_review_readiness_v1 import QA_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "crimson_primary_review_readiness_audit_v1.json"


class CrimsonPrimaryReviewReadinessV1Tests(unittest.TestCase):
    def test_real_inputs_recompute_exact_bounded_readiness(self) -> None:
        result = audit(CONFIG)
        self.assertEqual(result["status"], PASS_STATUS, result["errors"])
        self.assertEqual(result["counts"]["pending_primary_tasks"], 39)
        self.assertEqual(result["counts"]["ready_for_truthful_human_primary_review"], 24)
        self.assertEqual(result["counts"]["official_reference_followup_required"], 15)
        self.assertEqual(result["counts"]["second_review_required_after_primary"], 20)
        self.assertEqual(result["counts"]["human_decisions_created"], 0)
        self.assertFalse(result["decision"]["ai_may_impersonate_human_reviewer"])

    def test_written_report_is_fully_recomputed_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            report = write_report(CONFIG, output)
            qa = verify(CONFIG, output)
            self.assertEqual(report["status"], PASS_STATUS)
            self.assertEqual(qa["status"], QA_STATUS, qa["errors"])
            with self.assertRaises(FileExistsError):
                write_report(CONFIG, output)

    def test_tampered_packet_hash_fails_closed(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        config["inputs"][0]["sha256"] = "0" * 64
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            path = Path(handle.name)
        try:
            result = audit(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Input hash mismatch", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
