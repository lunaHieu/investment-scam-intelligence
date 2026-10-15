import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_manual_acquisition_packet_v1 import (
    validate_submission,
    verify,
)


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "configs" / "target_text_corpus_v1_manual_acquisition_packet_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ManualAcquisitionPacketTests(unittest.TestCase):
    def test_packet_is_instructions_only_and_keeps_all_data_gates_closed(self) -> None:
        result = verify(PACKET)
        self.assertEqual(result["source_count"], 3)
        self.assertTrue(result["dfpi_user_supplied_path_documented"])
        self.assertEqual(len(result["vietnamese_sources_blocked"]), 2)
        self.assertFalse(result["candidate_enumeration_allowed"])
        self.assertFalse(result["training_allowed"])

    def test_packet_rejects_premature_vietnamese_manual_capture(self) -> None:
        packet = json.loads(PACKET.read_text(encoding="utf-8"))
        changed = copy.deepcopy(packet)
        for item in changed["basis"]:
            path = Path(item["path"])
            if not path.is_absolute():
                item["path"] = str(ROOT / path)
        for key in ("schema_path", "template_path"):
            path = Path(changed["submission_manifest"][key])
            if not path.is_absolute():
                changed["submission_manifest"][key] = str(ROOT / path)
        source = next(
            item
            for item in changed["source_instructions"]
            if item["source_id"] == "ssc_vietnam_investor_warnings"
        )
        source["activation_status"] = "OPEN"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "opened prematurely"):
                verify(path)

    def test_dfpi_submission_verifies_exact_file_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path("dfpi_crypto_scam_tracker") / "2026-10-15" / "case.html"
            artifact = root / relative
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"first-party DFPI artifact")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            submission = {
                "submission_id": "DFPI_TEST_V1",
                "packet_id": "ISI_TARGET_TEXT_CORPUS_V1_MANUAL_ACQUISITION_PACKET_V1",
                "status": "PENDING_INDEPENDENT_INTAKE_QA",
                "created_at": "2026-10-15T02:30:00+07:00",
                "prepared_by": "test",
                "items": [
                    {
                        "item_id": "DFPI_ITEM_001",
                        "source_id": "dfpi_crypto_scam_tracker",
                        "official_source_url": "https://dfpi.ca.gov/consumers/crypto/crypto-scam-tracker/",
                        "acquisition_mode": "USER_SAVED_FIRST_PARTY_ARTIFACT",
                        "acquired_at": "2026-10-15T02:29:00+07:00",
                        "original_filename": "case.html",
                        "stored_relative_path": relative.as_posix(),
                        "media_type": "text/html",
                        "byte_size": artifact.stat().st_size,
                        "sha256": digest,
                        "rights_basis": {
                            "basis_type": "FIRST_PARTY_PUBLIC_RECORD_INTERNAL_RESEARCH",
                            "terms_or_permission_url": "https://dfpi.ca.gov/conditions-of-use/",
                            "local_evidence_relative_path": None,
                            "summary": "Internal test fixture."
                        },
                        "redistribution_permitted": False,
                        "contains_personal_data": True,
                        "notes": "UNCERTAIN"
                    }
                ]
            }
            submission_path = root / "submission.json"
            submission_path.write_text(json.dumps(submission), encoding="utf-8")
            result = validate_submission(PACKET, submission_path, root)
            self.assertEqual(result["item_count"], 1)
            self.assertTrue(result["files_and_hashes_verified"])
            self.assertFalse(result["candidate_or_label_created"])

    def test_submission_rejects_vietnamese_source_while_rights_gate_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            submission = {
                "submission_id": "SSC_BLOCKED_TEST",
                "packet_id": "ISI_TARGET_TEXT_CORPUS_V1_MANUAL_ACQUISITION_PACKET_V1",
                "status": "PENDING_INDEPENDENT_INTAKE_QA",
                "created_at": "2026-10-15T02:30:00+07:00",
                "prepared_by": "test",
                "items": [{"item_id": "SSC_ITEM", "source_id": "ssc_vietnam_investor_warnings"}]
            }
            submission_path = root / "submission.json"
            submission_path.write_text(json.dumps(submission), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "remains blocked"):
                validate_submission(PACKET, submission_path, root)

    def test_registry_hashes_are_current(self) -> None:
        registry_path = (
            ROOT
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_manual_acquisition_packet_v1.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertFalse(registry["decision"]["source_acquisition_executed"])
        self.assertFalse(registry["decision"]["candidate_enumeration_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
