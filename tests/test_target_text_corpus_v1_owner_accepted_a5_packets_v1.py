import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_target_text_corpus_v1_owner_accepted_a5_packets_v1 import _jsonl_bytes, build_packets
from scripts.verify_target_text_corpus_v1_owner_accepted_a5_fresh_cohort_v1 import verify as verify_fresh
from scripts.verify_target_text_corpus_v1_owner_accepted_a5_language_packet_v1 import verify as verify_language


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_owner_accepted_a5_packet_protocol_v1.json"


class OwnerAcceptedA5PacketsV1Tests(unittest.TestCase):
    def _fixture(self, directory: Path) -> tuple[Path, dict[str, Path]]:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        outputs = {
            "language_packet": directory / "language.jsonl",
            "language_report": directory / "language_report.json",
            "language_independent_qa": directory / "language_qa.json",
            "fresh_packet": directory / "fresh.jsonl",
            "fresh_report": directory / "fresh_report.json",
            "fresh_independent_qa": directory / "fresh_qa.json",
        }
        config["planned_outputs"] = {key: str(path) for key, path in outputs.items()}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            config_path = Path(handle.name)
        result = build_packets(config_path)
        outputs["language_packet"].write_bytes(_jsonl_bytes(result["language_rows"]))
        outputs["language_report"].write_text(json.dumps(result["language_report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs["fresh_packet"].write_bytes(_jsonl_bytes(result["fresh_rows"]))
        outputs["fresh_report"].write_text(json.dumps(result["fresh_report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return config_path, outputs

    def test_real_protocol_builds_two_exact_separate_packets_without_admission(self) -> None:
        result = build_packets(CONFIG)
        self.assertEqual(len(result["language_rows"]), 42)
        self.assertEqual(len(result["fresh_rows"]), 42)
        self.assertEqual(result["language_report"]["review_state"]["pending_human_review"], 42)
        self.assertEqual(result["fresh_report"]["assertion_state"]["fresh_cohort_asserted"], 42)
        self.assertEqual(result["language_report"]["decision"]["admission_credit_now"], 0)
        self.assertEqual(result["fresh_report"]["decision"]["admission_credit_now"], 0)

    def test_both_independent_verifiers_recompute_exact_population(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, outputs = self._fixture(Path(tmp))
            try:
                language = verify_language(config_path, outputs["language_packet"], outputs["language_report"])
                fresh = verify_fresh(config_path, outputs["fresh_packet"], outputs["fresh_report"])
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(language["status"], "PASS_LANGUAGE_PACKET_EXACT_42_HASH_RECOMPUTED_HUMAN_REVIEW_PENDING")
        self.assertEqual(fresh["status"], "PASS_FRESH_COHORT_PACKET_EXACT_42_FULLY_RECOMPUTED_NO_ADMISSION_CREDIT")
        self.assertFalse(language["decision"]["human_review_complete"])
        self.assertFalse(fresh["decision"]["channel_contribution_created"])

    def test_language_verifier_rejects_prefilled_ai_or_human_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, outputs = self._fixture(Path(tmp))
            rows = [json.loads(line) for line in outputs["language_packet"].read_text(encoding="utf-8").splitlines()]
            rows[0]["language_code"] = "en"
            rows[0]["human_reviewed_language"] = True
            outputs["language_packet"].write_bytes(_jsonl_bytes(rows))
            try:
                result = verify_language(config_path, outputs["language_packet"], outputs["language_report"])
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("fabricated" in error for error in result["errors"]))

    def test_fresh_verifier_rejects_unbound_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, outputs = self._fixture(Path(tmp))
            rows = [json.loads(line) for line in outputs["fresh_packet"].read_text(encoding="utf-8").splitlines()]
            rows[0]["availability_plan_id"] = "UNBOUND"
            outputs["fresh_packet"].write_bytes(_jsonl_bytes(rows))
            try:
                result = verify_fresh(config_path, outputs["fresh_packet"], outputs["fresh_report"])
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("recomputation" in error for error in result["errors"]))

    def test_protocol_rejects_language_builder_impersonation(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(config)
        tampered["language_review_contract"]["builder_may_set_human_reviewed_language_true"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(tampered, handle)
            path = Path(handle.name)
        try:
            with self.assertRaisesRegex(PermissionError, "fabricate"):
                build_packets(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
