"""Verify the frozen Target Text Corpus V1 schema/review pilot protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_SCHEMA_REVIEW_PILOT_V1"
EXPECTED_STATUS = "FROZEN_SCHEMA_REVIEW_PILOT_PROTOCOL_COMPLETE_ENUMERATION_BLOCKED"
CHANNELS = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": {
        "stratum": "CONFIRMED",
        "sources": {"iosco_i_scan", "fca_warning_list", "ubcknn_warnings"},
        "reference_role": "CANDIDATE_DISCOVERY_AND_CASE_EVIDENCE_ONLY",
    },
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": {
        "stratum": "CONFIRMED",
        "sources": {"cftc_red_list"},
        "reference_role": "CANDIDATE_DISCOVERY_AND_CASE_EVIDENCE_ONLY",
    },
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": {
        "stratum": "LEGITIMATE",
        "sources": {"sec_iapd"},
        "reference_role": "OFFICIAL_ENTITY_REFERENCE_ONLY",
    },
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": {
        "stratum": "LEGITIMATE",
        "sources": {"sec_edgar_company_submissions"},
        "reference_role": "OFFICIAL_ENTITY_REFERENCE_ONLY",
    },
}
EXPECTED_SAFETY = {
    "network_operations": 0,
    "domain_access_allowed": False,
    "candidate_records_enumerated": 0,
    "new_records_acquired": 0,
    "new_artifact_captures": 0,
    "labels_created": 0,
    "labels_changed": 0,
    "model_fit_operations": 0,
    "model_scoring_operations": 0,
    "validation_or_test_openings": 0,
    "training_allowed": False,
    "deployment_allowed": False,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def _https(value: object) -> bool:
    parsed = urlparse(str(value))
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_candidate(candidate: dict[str, Any]) -> list[str]:
    """Validate invariants that keep an enumerated candidate unlabeled and safe."""
    errors: list[str] = []
    required = {
        "schema_version",
        "candidate_id",
        "enumeration_wave_id",
        "channel_id",
        "channel_target_stratum",
        "predicted_artifact_type",
        "reference",
        "candidate_identity",
        "enumerated_at",
        "queue_state",
        "exclusion_screen",
        "capture_plan",
        "review_state",
        "safety",
    }
    missing = sorted(required - set(candidate))
    extra = sorted(set(candidate) - required)
    if missing:
        errors.append(f"Missing candidate fields: {missing}")
    if extra:
        errors.append(f"Unexpected candidate fields: {extra}")
    channel_id = candidate.get("channel_id")
    channel = CHANNELS.get(str(channel_id))
    if channel is None:
        errors.append("Unknown channel ID")
    elif candidate.get("channel_target_stratum") != channel["stratum"]:
        errors.append("Channel target stratum mismatch")
    if candidate.get("schema_version") != "target_text_candidate_v1":
        errors.append("Candidate schema version changed")
    if not re.fullmatch(r"TTCV1_CAND_[A-Z0-9_-]+", str(candidate.get("candidate_id", ""))):
        errors.append("Invalid candidate ID")
    if not re.fullmatch(r"TTCV1_ENUM_[A-Z0-9_-]+", str(candidate.get("enumeration_wave_id", ""))):
        errors.append("Invalid enumeration wave ID")
    if candidate.get("predicted_artifact_type") != "WEBSITE_SNAPSHOT":
        errors.append("Candidate artifact modality changed")
    if candidate.get("queue_state") != "PROVENANCE_ENUMERATED_UNCAPTURED":
        errors.append("Candidate queue state changed")

    reference = candidate.get("reference", {})
    if not isinstance(reference, dict):
        errors.append("Reference must be an object")
    else:
        if channel is not None and reference.get("source_id") not in channel["sources"]:
            errors.append("Reference source is not registered for the channel")
        if channel is not None and reference.get("reference_role") != channel["reference_role"]:
            errors.append("Reference role mismatch")
        if not reference.get("source_record_id"):
            errors.append("Reference record ID missing")
        if not _https(reference.get("source_url")):
            errors.append("Reference URL must be HTTPS")
        if not re.fullmatch(r"[a-f0-9]{64}", str(reference.get("reference_sha256", ""))):
            errors.append("Reference SHA-256 invalid")

    identity = candidate.get("candidate_identity", {})
    if not isinstance(identity, dict):
        errors.append("Candidate identity must be an object")
    else:
        parsed = urlparse(str(identity.get("candidate_url", "")))
        normalized_host = str(identity.get("normalized_host", "")).lower()
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            errors.append("Candidate URL invalid")
        elif parsed.hostname.lower() != normalized_host:
            errors.append("Candidate URL host does not match normalized host")
        expected_host_hash = hashlib.sha256(normalized_host.encode("utf-8")).hexdigest()
        if identity.get("normalized_host_sha256") != expected_host_hash:
            errors.append("Normalized-host SHA-256 mismatch")
        for field in ("entity_name_from_reference", "identity_linkage_basis"):
            if not str(identity.get(field, "")).strip():
                errors.append(f"Candidate identity field missing: {field}")

    expected_exclusion = {
        "opened_normalized_host": "PASS",
        "opened_reference_identity": "PASS",
        "exact_capture": "PENDING_CAPTURE",
        "exact_text": "PENDING_CAPTURE",
        "case_campaign_entity_family": "PENDING_REVIEW",
        "near_duplicate": "PENDING_CAPTURE",
    }
    exclusion = candidate.get("exclusion_screen", {})
    for field, expected in expected_exclusion.items():
        if not isinstance(exclusion, dict) or exclusion.get(field) != expected:
            errors.append(f"Candidate exclusion state invalid: {field}")
    if not isinstance(exclusion, dict) or exclusion.get("legacy_component") not in {
        "PASS",
        "MANUAL_CLEARED",
    }:
        errors.append("Legacy-component exclusion state invalid")

    expected_capture = {
        "capture_source": "WAYBACK_MACHINE",
        "live_candidate_domain_access_allowed": False,
        "automatic_external_redirect_following": False,
        "raw_capture_overwrite_allowed": False,
    }
    if candidate.get("capture_plan") != expected_capture:
        errors.append("Candidate capture plan changed")
    expected_review = {
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
    }
    if candidate.get("review_state") != expected_review:
        errors.append("Candidate review state is not closed and unlabeled")
    expected_candidate_safety = {
        "live_domain_accessed": False,
        "wayback_queried": False,
        "model_scored": False,
    }
    if candidate.get("safety") != expected_candidate_safety:
        errors.append("Candidate safety state changed")
    return errors


def validate_protocol(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    errors: list[str] = []
    checked: list[dict[str, object]] = []
    for item in protocol.get("basis", []):
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Basis artifact missing or changed: {item.get('role')}")

    schema_info = protocol.get("candidate_schema", {})
    schema_path = resolve(root, schema_info.get("path", ""))
    if not schema_path.is_file():
        errors.append("Candidate schema missing")
        schema: dict[str, Any] = {}
    else:
        schema = load_json(schema_path)
        checked.append({"role": "candidate_schema", "path": str(schema_path), "sha256": sha256_file(schema_path)})
    if schema.get("additionalProperties") is not False:
        errors.append("Candidate schema must reject additional properties")
    schema_required = set(schema.get("required", []))
    if not {"channel_id", "reference", "candidate_identity", "review_state", "safety"}.issubset(
        schema_required
    ):
        errors.append("Candidate schema required fields incomplete")
    for field in (
        "candidate_is_a_label",
        "candidate_is_a_case",
        "candidate_is_a_training_row",
        "artifact_text_allowed",
        "warning_or_filing_text_allowed_as_predicted_artifact",
    ):
        if schema_info.get(field) is not False:
            errors.append(f"Candidate schema guard changed: {field}")

    wave = protocol.get("initial_enumeration_wave", {})
    quotas = wave.get("quota_by_channel", {})
    if quotas != {channel: 10 for channel in CHANNELS}:
        errors.append("Initial channel quotas changed")
    if wave.get("candidate_record_target") != 40:
        errors.append("Initial candidate target changed")
    if wave.get("candidate_records_by_target_stratum") != {"CONFIRMED": 20, "LEGITIMATE": 20}:
        errors.append("Initial target-stratum balance changed")
    if wave.get("maximum_candidate_fraction_from_one_channel_per_target_stratum") != 0.5:
        errors.append("Channel concentration cap changed")
    if wave.get("quota_shortfall_policy") != "FAIL_WAVE_DO_NOT_REALLOCATE_ACROSS_CHANNELS":
        errors.append("Quota shortfall policy changed")

    selection = protocol.get("selection_contract", {})
    if selection.get("manual_cherry_picking_allowed") is not False:
        errors.append("Manual cherry-picking opened")
    if selection.get("model_score_ranking_allowed") is not False:
        errors.append("Model-score ranking opened")
    if selection.get("cross_channel_host_overlap_allowed") is not False:
        errors.append("Cross-channel host overlap opened")

    prerequisites = protocol.get("channel_prerequisites", {})
    if set(prerequisites) != set(CHANNELS):
        errors.append("Channel prerequisite set changed")
    expected_ready = {
        "CONFIRMED_REGULATOR_LINKED_WEBSITE": True,
        "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": False,
        "LEGITIMATE_REGISTER_LINKED_WEBSITE": True,
        "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": False,
    }
    for channel, ready in expected_ready.items():
        item = prerequisites.get(channel, {})
        if item.get("reference_inputs_ready") is not ready:
            errors.append(f"Channel readiness changed: {channel}")
        if item.get("enumeration_allowed_after_protocol_verification") is not ready:
            errors.append(f"Channel enumeration readiness changed: {channel}")
    release = protocol.get("wave_release_rule", {})
    if release.get("partial_channel_enumeration_allowed") is not False:
        errors.append("Partial-channel release opened")
    if release.get("all_four_channel_inputs_required_before_initial_wave") is not True:
        errors.append("All-channel release requirement changed")

    review = protocol.get("review_contract", {})
    if review.get("independent_second_review_required_for_every_binary_eligible_record") is not True:
        errors.append("Independent second review requirement changed")
    if review.get("second_reviewer_receives_first_review_rationale") is not False:
        errors.append("Blind-review boundary changed")
    if review.get("model_prediction_visible_to_reviewer") is not False:
        errors.append("Model predictions exposed to reviewer")
    if review.get("warning_list_or_registry_membership_alone_sufficient_for_label") is not False:
        errors.append("Reference-only labeling opened")

    acceptance = protocol.get("pilot_acceptance_gate", {})
    if acceptance.get("unit") != "TRANSITIVE_GROUP":
        errors.append("Pilot acceptance unit changed")
    if acceptance.get("minimum_eligible_groups_by_ground_truth_status") != {
        "CONFIRMED": 20,
        "LEGITIMATE": 20,
    }:
        errors.append("Pilot label-group target changed")
    if acceptance.get("minimum_eligible_groups_by_channel") != {
        channel: 10 for channel in CHANNELS
    }:
        errors.append("Pilot channel-group target changed")
    if acceptance.get("initial_40_candidates_guarantee_gate_pass") is not False:
        errors.append("Candidate count incorrectly guarantees the pilot gate")
    if acceptance.get("model_training_allowed_when_pilot_passes") is not False:
        errors.append("Pilot improperly opens training")

    reserve = protocol.get("reserve_policy", {})
    if reserve.get("batch_size_per_deficient_channel") != 5:
        errors.append("Reserve batch size changed")
    if reserve.get("cross_channel_quota_reallocation_allowed") is not False:
        errors.append("Cross-channel reserve reallocation opened")
    if reserve.get("failed_or_uncertain_candidates_may_not_be_replaced_in_place") is not True:
        errors.append("In-place candidate replacement opened")

    gates = protocol.get("gate_status", {})
    if gates.get("protocol_frozen") is not True or gates.get("candidate_schema_frozen") is not True:
        errors.append("Protocol/schema freeze not recorded")
    for gate in (
        "all_channel_prerequisites_ready",
        "candidate_enumeration_allowed",
        "candidate_capture_allowed",
        "binary_labeling_allowed",
        "pilot_passed",
    ):
        if gates.get(gate) is not False:
            errors.append(f"Gate unexpectedly open: {gate}")
    if protocol.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Protocol safety contract changed")

    return {
        "valid": not errors,
        "protocol_id": protocol.get("protocol_id"),
        "status": protocol.get("status"),
        "checked_artifact_count": len(checked),
        "candidate_schema_frozen": gates.get("candidate_schema_frozen"),
        "initial_candidate_target": wave.get("candidate_record_target"),
        "quota_by_channel": quotas,
        "ready_channel_count": sum(expected_ready.values()),
        "blocked_channel_count": sum(not value for value in expected_ready.values()),
        "candidate_enumeration_allowed": gates.get("candidate_enumeration_allowed"),
        "model_fit_operations": 0,
        "errors": errors,
        "checked": checked,
    }


def verify_registry(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, object]] = []
    role_paths: dict[str, Path] = {}
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected registry status")
    items = (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    )
    for item in items:
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        if role in role_paths:
            errors.append(f"Duplicate artifact role: {role}")
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    protocol_path = role_paths.get("schema_review_pilot_protocol")
    protocol_result: dict[str, Any] = {}
    if protocol_path is None:
        errors.append("Schema/review pilot protocol missing")
    else:
        protocol_result = validate_protocol(protocol_path)
        errors.extend(protocol_result["errors"])
    if registry.get("safety_contract") != EXPECTED_SAFETY:
        errors.append("Registry safety contract changed")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "initial_candidate_target": protocol_result.get("initial_candidate_target"),
        "ready_channel_count": protocol_result.get("ready_channel_count"),
        "blocked_channel_count": protocol_result.get("blocked_channel_count"),
        "candidate_enumeration_allowed": False,
        "model_fit_operations": 0,
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    if (args.protocol is None) == (args.registry is None):
        parser.error("provide exactly one of --protocol or --registry")
    result = (
        validate_protocol(args.protocol)
        if args.protocol is not None
        else verify_registry(args.registry)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
