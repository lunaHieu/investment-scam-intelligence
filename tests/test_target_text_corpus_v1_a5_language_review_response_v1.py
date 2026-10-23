import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_target_text_corpus_v1_a5_language_review_response_v1 import _json_bytes, prepare
from scripts.verify_target_text_corpus_v1_a5_language_review_response_tooling_v1 import verify as verify_tooling
from scripts.verify_target_text_corpus_v1_a5_language_review_response_v1 import verify as verify_response


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_a5_language_review_response_protocol_v1.json"


class A5LanguageReviewResponseV1Tests(unittest.TestCase):
    def _fixture(self, directory: Path) -> tuple[Path, dict[str, Path], dict]:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        outputs = {key: directory / Path(value).name for key, value in config["planned_outputs"].items()}
        config["planned_outputs"] = {key: str(value) for key, value in outputs.items()}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            config_path = Path(handle.name)
        prepared = prepare(config_path)
        template = prepared["template"]
        outputs["response_template"].write_bytes(_json_bytes(template))
        import hashlib
        from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file
        report = {
            "report_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_RESPONSE_PREPARATION_REPORT_V1",
            "status": "PASS_C3_TEMPLATE_PREPARED_HUMAN_RESPONSE_ABSENT",
            "protocol_sha256": sha256_file(config_path),
            "template_sha256": hashlib.sha256(_json_bytes(template)).hexdigest(),
            "population": {"records": 42, "development": 33, "external_holdout": 9},
            "review_state": {"pending_human_review": 42, "completed_human_review": 0},
            "decision": {"tooling_ready": True, "human_response_exists": False, "language_supply_credit_now": 0, "training_allowed": False},
            "safety_contract": {"network_operations": 0, "human_decisions_fabricated": 0, "labels_changed": 0, "model_operations": 0},
        }
        outputs["preparation_report"].write_bytes(_json_bytes(report))
        return config_path, outputs, template

    @staticmethod
    def _completed(template: dict) -> dict:
        response = copy.deepcopy(template)
        response.update({
            "response_id": "TEST_SYNTHETIC_CONTRACT_EXERCISE_ONLY",
            "status": "COMPLETED_HUMAN_LANGUAGE_REVIEW_PENDING_INDEPENDENT_QA",
            "created_at": "2026-10-23T12:00:00+07:00",
        })
        response["reviewer"] = {
            "reviewer_id": "TEST_FIXTURE_HUMAN_ROLE",
            "reviewer_type": "HUMAN",
            "independent_human_attestation": True,
            "hash_verified_visible_text_attestation": True,
            "automatic_or_ai_hint_used_as_final": False,
        }
        for row in response["records"]:
            row.update({
                "language_code": "en",
                "human_reviewed_language": True,
                "review_status": "COMPLETED_HUMAN_LANGUAGE_REVIEW",
                "reviewed_at": "2026-10-23T12:00:00+07:00",
                "rationale": "Synthetic unit-test value; no production review claim.",
            })
        return response

    def test_real_protocol_prepares_exact_pending_template(self) -> None:
        result = prepare(CONFIG)
        self.assertEqual(len(result["template"]["records"]), 42)
        self.assertTrue(all(row["language_code"] is None for row in result["template"]["records"]))
        self.assertEqual(result["template"]["status"], "TEMPLATE_NOT_A_COMPLETED_RESPONSE")

    def test_tooling_verifier_recomputes_template_and_preserves_human_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, outputs, _ = self._fixture(Path(tmp))
            try:
                result = verify_tooling(config_path, outputs["response_template"], outputs["preparation_report"])
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "PASS_C3_PREFLIGHT_EXACT_42_TEMPLATE_AND_VERIFIER_READY_HUMAN_RESPONSE_ABSENT")
        self.assertFalse(result["decision"]["c3_human_response_complete"])

    def test_response_verifier_accepts_only_exact_hash_bound_complete_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, outputs, template = self._fixture(Path(tmp))
            response_path = Path(tmp) / "response.json"
            response_path.write_bytes(_json_bytes(self._completed(template)))
            try:
                result = verify_response(config_path, response_path)
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "PASS_EXACT_42_HUMAN_LANGUAGE_RESPONSE_HASH_RECOMPUTED")
        self.assertEqual(result["checks"]["records_verified"], 42)
        self.assertEqual(result["decision"]["labels_changed"], 0)

    def test_response_verifier_rejects_ai_reviewer_and_hash_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, template = self._fixture(Path(tmp))
            response = self._completed(template)
            response["reviewer"]["reviewer_type"] = "AI"
            response["records"][0]["source_text_sha256"] = "0" * 64
            response_path = Path(tmp) / "response.json"
            response_path.write_bytes(_json_bytes(response))
            try:
                result = verify_response(config_path, response_path)
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("human attestation" in error for error in result["errors"]))
        self.assertTrue(any("Hash-bound field changed" in error for error in result["errors"]))

    def test_schema_rejects_extra_fields_and_binds_exact_count(self) -> None:
        schema = json.loads((ROOT / "schemas" / "target_text_a5_language_review_response_v1.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["records"]["minItems"], 42)
        self.assertEqual(schema["properties"]["records"]["maxItems"], 42)
        self.assertEqual(schema["properties"]["reviewer"]["properties"]["reviewer_type"]["const"], "HUMAN")


if __name__ == "__main__":
    unittest.main()
