import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_target_text_corpus_v1_c2_external_artifact_intake_v1 import _json_bytes, prepare
from scripts.verify_target_text_corpus_v1_c2_external_artifact_intake_v1 import validate_submission, verify_tooling
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_c2_external_artifact_intake_protocol_v1.json"


class C2ExternalArtifactIntakeV1Tests(unittest.TestCase):
    def _fixture(self, directory: Path) -> tuple[Path, dict[str, Path], dict]:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        data_root = directory / "data"
        config["storage_contract"]["data_root"] = str(data_root)
        outputs = {key: directory / Path(value).name for key, value in config["planned_outputs"].items()}
        config["planned_outputs"] = {key: str(value) for key, value in outputs.items()}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            config_path = Path(handle.name)
        prepared = prepare(config_path)
        outputs["submission_template"].write_bytes(_json_bytes(prepared["template"]))
        report = {
            "report_id": "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_INTAKE_PREPARATION_REPORT_V1",
            "status": "PASS_C2_INTAKE_TEMPLATE_PREPARED_EXTERNAL_INPUTS_ABSENT",
            "protocol_sha256": sha256_file(config_path),
            "template_sha256": hashlib.sha256(_json_bytes(prepared["template"])).hexdigest(),
            "source_contracts": 4,
            "source_artifact_channels_open_for_qa": ["cftc_red_list", "dfpi_crypto_scam_tracker"],
            "rights_record_only_channels": ["hnx_vietnam_issuer_profiles", "ssc_vietnam_investor_warnings"],
            "decision": {"tooling_ready": True, "completed_submission_exists": False, "source_files_acquired": 0, "rights_records_acquired": 0, "training_allowed": False},
            "safety_contract": {"network_operations": 0, "candidate_records_enumerated": 0, "labels_changed": 0, "model_operations": 0},
        }
        outputs["preparation_report"].write_bytes(_json_bytes(report))
        return config_path, outputs, config

    @staticmethod
    def _submission(item: dict) -> dict:
        return {
            "submission_id": "TEST_SYNTHETIC_C2_SUBMISSION",
            "protocol_id": "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_INTAKE_PROTOCOL_V1",
            "status": "PENDING_INDEPENDENT_C2_INTAKE_QA",
            "created_at": "2026-10-23T12:00:00+07:00",
            "prepared_by": "TEST_FIXTURE",
            "items": [item],
        }

    def _item(self, data_root: Path, source_id: str, item_type: str) -> dict:
        if source_id == "cftc_red_list":
            relative = "raw/cftc_red_list/2026-10-23/sample.json"
            source_url = "https://www.cftc.gov/LearnAndProtect/Resources/Check/redlist.htm"
            mode = "USER_SUPPLIED_UNTOUCHED_ARTIFACT"
            basis = "FIRST_PARTY_PUBLIC_RECORD_INTERNAL_RESEARCH"
        else:
            relative = "governance/target_text_corpus_v1/external_rights_evidence/ssc_vietnam_investor_warnings/2026-10-23/permission.txt"
            source_url = "https://ssc.gov.vn/webcenter/portal/ubck/pages_r/m/nhadautu/khuyencaonhadautu"
            mode = "WRITTEN_PERMISSION"
            basis = "WRITTEN_PERMISSION"
        path = data_root.joinpath(*Path(relative).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic-test-bytes")
        return {
            "item_id": f"TEST_{source_id}",
            "item_type": item_type,
            "source_id": source_id,
            "official_source_url": source_url,
            "acquisition_mode": mode,
            "acquired_at": "2026-10-23T12:00:00+07:00",
            "original_filename": path.name,
            "stored_relative_path": relative,
            "media_type": "application/octet-stream",
            "byte_size": path.stat().st_size,
            "sha256": sha256_file(path),
            "rights_basis": {"basis_type": basis, "terms_or_permission_url": source_url, "summary": "Synthetic unit-test basis only."},
            "prerequisite_rights_registry_path": None,
            "redistribution_permitted": False,
            "contains_personal_data": False,
            "notes": "Synthetic unit-test item.",
        }

    def test_real_protocol_prepares_non_submission_for_four_sources(self) -> None:
        prepared = prepare(CONFIG)
        self.assertEqual(len(prepared["config"]["source_contracts"]), 4)
        self.assertEqual(prepared["template"]["status"], "TEMPLATE_NOT_A_SUBMISSION")
        self.assertFalse(prepared["config"]["decision"]["candidate_enumeration_allowed"])

    def test_tooling_verifier_recomputes_template_and_absent_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, outputs, _ = self._fixture(Path(tmp))
            try:
                result = verify_tooling(config_path, outputs["submission_template"], outputs["preparation_report"])
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "PASS_C2_PREFLIGHT_FOUR_SOURCE_INTAKE_READY_EXTERNAL_INPUTS_ABSENT")
        self.assertFalse(result["decision"]["c2_intake_complete"])

    def test_cftc_source_artifact_recomputes_bytes_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, config = self._fixture(Path(tmp))
            data_root = Path(config["storage_contract"]["data_root"])
            item = self._item(data_root, "cftc_red_list", "SOURCE_ARTIFACT")
            submission_path = Path(tmp) / "submission.json"
            submission_path.write_bytes(_json_bytes(self._submission(item)))
            try:
                result = validate_submission(config_path, submission_path, data_root)
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "PASS_C2_SUBMISSION_BYTES_HASHES_SOURCE_AND_RIGHTS_RECOMPUTED")
        self.assertEqual(result["type_counts"]["SOURCE_ARTIFACT"], 1)
        self.assertFalse(result["decision"]["candidate_enumeration_allowed"])

    def test_ssc_rights_record_passes_but_source_artifact_stays_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, config = self._fixture(Path(tmp))
            data_root = Path(config["storage_contract"]["data_root"])
            item = self._item(data_root, "ssc_vietnam_investor_warnings", "RIGHTS_EVIDENCE_RECORD")
            submission_path = Path(tmp) / "rights.json"
            submission_path.write_bytes(_json_bytes(self._submission(item)))
            try:
                result = validate_submission(config_path, submission_path, data_root)
                item["item_type"] = "SOURCE_ARTIFACT"
                item["acquisition_mode"] = "EXPLICIT_OFFICIAL_EXPORT"
                blocked_path = Path(tmp) / "blocked.json"
                blocked_path.write_bytes(_json_bytes(self._submission(item)))
                with self.assertRaisesRegex(ValueError, "separate rights-readiness ledger"):
                    validate_submission(config_path, blocked_path, data_root)
            finally:
                config_path.unlink(missing_ok=True)
        self.assertEqual(result["type_counts"]["RIGHTS_EVIDENCE_RECORD"], 1)

    def test_hash_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, config = self._fixture(Path(tmp))
            data_root = Path(config["storage_contract"]["data_root"])
            item = self._item(data_root, "cftc_red_list", "SOURCE_ARTIFACT")
            item["sha256"] = "0" * 64
            submission_path = Path(tmp) / "submission.json"
            submission_path.write_bytes(_json_bytes(self._submission(item)))
            try:
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    validate_submission(config_path, submission_path, data_root)
            finally:
                config_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
