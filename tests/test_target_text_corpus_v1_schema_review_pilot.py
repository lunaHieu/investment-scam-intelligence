import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.verify_target_text_corpus_v1_schema_review_pilot import (
    validate_candidate,
    validate_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_schema_review_pilot_v1.json"


def candidate() -> dict:
    host = "candidate.example"
    return {
        "schema_version": "target_text_candidate_v1",
        "candidate_id": "TTCV1_CAND_TEST_001",
        "enumeration_wave_id": "TTCV1_ENUM_PILOT_INITIAL_40",
        "channel_id": "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE",
        "channel_target_stratum": "CONFIRMED",
        "predicted_artifact_type": "WEBSITE_SNAPSHOT",
        "reference": {
            "source_id": "cftc_red_list",
            "source_record_id": "TEST-001",
            "source_url": "https://www.cftc.gov/example",
            "reference_role": "CANDIDATE_DISCOVERY_AND_CASE_EVIDENCE_ONLY",
            "reference_observed_at": "2026-10-03T10:00:00+07:00",
            "reference_sha256": "a" * 64,
        },
        "candidate_identity": {
            "entity_name_from_reference": "Example Entity",
            "candidate_url": f"http://{host}/",
            "normalized_host": host,
            "normalized_host_sha256": hashlib.sha256(host.encode("utf-8")).hexdigest(),
            "identity_linkage_basis": "Exact domain printed in the reference record.",
        },
        "enumerated_at": "2026-10-03T10:00:00+07:00",
        "queue_state": "PROVENANCE_ENUMERATED_UNCAPTURED",
        "exclusion_screen": {
            "opened_normalized_host": "PASS",
            "opened_reference_identity": "PASS",
            "legacy_component": "PASS",
            "exact_capture": "PENDING_CAPTURE",
            "exact_text": "PENDING_CAPTURE",
            "case_campaign_entity_family": "PENDING_REVIEW",
            "near_duplicate": "PENDING_CAPTURE",
        },
        "capture_plan": {
            "capture_source": "WAYBACK_MACHINE",
            "live_candidate_domain_access_allowed": False,
            "automatic_external_redirect_following": False,
            "raw_capture_overwrite_allowed": False,
        },
        "review_state": {
            "artifact_capture": "MISSING",
            "identity_resolution": "UNRESOLVED",
            "ground_truth_status": "UNCERTAIN",
            "label_confidence": "LOW",
            "review_status": "UNREVIEWED",
            "primary_review": "NOT_STARTED",
            "independent_second_review": "NOT_STARTED",
            "owner_acceptance": "NOT_REQUESTED",
            "training_eligible": "NO",
            "label_created": False,
        },
        "safety": {
            "live_domain_accessed": False,
            "wayback_queried": False,
            "model_scored": False,
        },
    }


class TargetTextCorpusSchemaReviewPilotTests(unittest.TestCase):
    def test_frozen_protocol_passes(self):
        result = validate_protocol(PROTOCOL)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["initial_candidate_target"], 40)
        self.assertEqual(result["ready_channel_count"], 2)
        self.assertEqual(result["blocked_channel_count"], 2)
        self.assertFalse(result["candidate_enumeration_allowed"])

    def test_candidate_contract_accepts_closed_unlabeled_record(self):
        self.assertEqual(validate_candidate(candidate()), [])

    def test_candidate_contract_rejects_label_or_live_access(self):
        value = deepcopy(candidate())
        value["review_state"]["ground_truth_status"] = "CONFIRMED"
        value["review_state"]["label_created"] = True
        value["capture_plan"]["live_candidate_domain_access_allowed"] = True
        errors = validate_candidate(value)
        self.assertTrue(any("review state" in error.lower() for error in errors))
        self.assertTrue(any("capture plan" in error.lower() for error in errors))

    def test_schema_has_no_artifact_text_field(self):
        schema = json.loads(
            (ROOT / "schemas" / "target_text_candidate.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("text", schema["properties"])
        self.assertNotIn("ground_truth_status", schema["properties"])

    def test_protocol_keeps_training_and_all_execution_gates_closed(self):
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertFalse(protocol["gate_status"]["candidate_enumeration_allowed"])
        self.assertFalse(protocol["gate_status"]["candidate_capture_allowed"])
        self.assertFalse(protocol["gate_status"]["binary_labeling_allowed"])
        self.assertFalse(protocol["pilot_acceptance_gate"]["model_training_allowed_when_pilot_passes"])
        self.assertEqual(protocol["safety_contract"]["network_operations"], 0)
        self.assertEqual(protocol["safety_contract"]["candidate_records_enumerated"], 0)
        self.assertEqual(protocol["safety_contract"]["model_fit_operations"], 0)


if __name__ == "__main__":
    unittest.main()
