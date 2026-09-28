"""Controlled reviewer-decision records for external-text reconciliation."""

from __future__ import annotations

import copy
from datetime import datetime


BRANCH_RULES = {
    "CONFIRMED": {
        "target_decision": "CONFIRMED",
        "required_checks": [
            "raw_and_text_hashes_verified",
            "archived_candidate_artifact_reviewed",
            "candidate_identity_and_host_reconciled",
            "official_warning_opened_or_locally_verified",
            "warning_candidate_scope_reviewed",
            "domain_repurpose_or_injected_content_reviewed",
            "contradictory_evidence_review_complete",
        ],
    },
    "LEGITIMATE": {
        "target_decision": "LEGITIMATE",
        "required_checks": [
            "raw_and_text_hashes_verified",
            "captured_candidate_artifact_reviewed",
            "sec_iapd_record_and_crd_verified",
            "filed_host_and_identity_reconciled",
            "site_control_at_capture_time_reviewed",
            "impersonation_or_compromise_reviewed",
            "adverse_regulator_evidence_reviewed",
            "contradictory_evidence_review_complete",
        ],
    },
}


def build_pending_review_record(
    packet_record: dict[str, object],
    *,
    branch: str,
    packet_analysis_id: str,
    packet_sha256: str,
) -> dict[str, object]:
    """Convert one verified second-pass record into a blank human-review form."""

    if branch not in BRANCH_RULES:
        raise ValueError(f"Unsupported branch: {branch}")
    source_state = packet_record.get("source_state", {})
    if (
        source_state.get("ground_truth_status") != "UNCERTAIN"
        or source_state.get("label_confidence") != "LOW"
        or source_state.get("review_status") != "IN_REVIEW"
        or source_state.get("record_state_changed") is not False
    ):
        raise ValueError("Packet record is not a frozen UNCERTAIN draft")
    contradiction = packet_record.get("contradiction_review", {})
    if contradiction.get("hard_contradictions") != []:
        raise ValueError("Cannot prepare a decision form with a hard contradiction")
    proposal = packet_record.get("automated_second_pass", {})
    target = BRANCH_RULES[branch]["target_decision"]
    if proposal.get("proposed_outcome_for_human_review") != target:
        raise ValueError("Packet proposal and review branch do not align")
    if proposal.get("recommendation_is_ground_truth") is not False:
        raise ValueError("Packet recommendation was already promoted to ground truth")
    if packet_record.get("external_evaluation_eligible") is not False:
        raise ValueError("Packet record already opened external eligibility")

    case_id = str(packet_record.get("case_id", ""))
    if not case_id:
        raise ValueError("Packet record is missing case_id")
    required_checks = list(BRANCH_RULES[branch]["required_checks"])
    return {
        "review_form_id": f"EXTTEXT_REVIEW_{case_id}_V1",
        "case_id": case_id,
        "branch": branch,
        "candidate_host": packet_record.get("candidate_host"),
        "source_packet": {
            "analysis_id": packet_analysis_id,
            "sha256": packet_sha256,
        },
        "automated_context": {
            "proposed_outcome": target,
            "recommendation_confidence": proposal.get("recommendation_confidence"),
            "caution_flags": list(contradiction.get("caution_flags", [])),
            "hard_contradictions": [],
            "recommendation_is_ground_truth": False,
        },
        "review_contract": {
            "allowed_final_decisions": [target, "UNCERTAIN"],
            "allowed_confidence": ["HIGH", "MEDIUM", "LOW"],
            "required_checks": required_checks,
            "target_decision_requires_high_confidence_for_materialization": True,
        },
        "evidence_confirmations": {name: None for name in required_checks},
        "human_review": {
            "status": "PENDING",
            "final_decision": None,
            "label_confidence": None,
            "reviewer": None,
            "reviewed_at": None,
            "rationale": None,
            "confirmation_source": None,
            "unresolved_contradictions": [],
            "human_confirmation_recorded": False,
        },
        "ready_for_reconciled_intake": False,
        "source_intake_changed": False,
        "label_created": False,
        "external_evaluation_eligible": False,
    }


def record_human_decision(
    review_record: dict[str, object],
    *,
    decision: str,
    confidence: str,
    reviewer: str,
    reviewed_at: str,
    rationale: str,
    confirmation_source: str,
    confirm_all_checks: bool,
    confirm_human_review: bool,
    unresolved_contradictions: list[str] | None = None,
) -> dict[str, object]:
    """Return a completed review record without modifying source intake or labels."""

    if review_record.get("human_review", {}).get("status") != "PENDING":
        raise ValueError("Review record is not pending")
    if not confirm_human_review:
        raise ValueError("Explicit human-review confirmation is required")
    if not confirm_all_checks:
        raise ValueError("All branch-specific evidence checks must be explicitly confirmed")
    allowed_decisions = review_record.get("review_contract", {}).get(
        "allowed_final_decisions", []
    )
    if decision not in allowed_decisions:
        raise ValueError(f"Decision {decision} is not allowed for this branch")
    if confidence not in review_record.get("review_contract", {}).get(
        "allowed_confidence", []
    ):
        raise ValueError(f"Unsupported confidence: {confidence}")
    for name, value in (
        ("reviewer", reviewer),
        ("rationale", rationale),
        ("confirmation_source", confirmation_source),
    ):
        if not value.strip():
            raise ValueError(f"{name} is required")
    try:
        datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be an ISO-8601 date or timestamp") from exc

    unresolved = [item.strip() for item in (unresolved_contradictions or []) if item.strip()]
    target = str(review_record["automated_context"]["proposed_outcome"])
    if decision == target and unresolved:
        raise ValueError("A target decision cannot retain unresolved contradictions")

    output = copy.deepcopy(review_record)
    output["evidence_confirmations"] = {
        name: True for name in output["review_contract"]["required_checks"]
    }
    output["human_review"] = {
        "status": "COMPLETED",
        "final_decision": decision,
        "label_confidence": confidence,
        "reviewer": reviewer.strip(),
        "reviewed_at": reviewed_at,
        "rationale": rationale.strip(),
        "confirmation_source": confirmation_source.strip(),
        "unresolved_contradictions": unresolved,
        "human_confirmation_recorded": True,
    }
    output["ready_for_reconciled_intake"] = bool(
        decision == target and confidence == "HIGH" and not unresolved
    )
    output["source_intake_changed"] = False
    output["label_created"] = False
    output["external_evaluation_eligible"] = False
    return output
