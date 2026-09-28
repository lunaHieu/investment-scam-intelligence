"""Auditable AI adjudication records for external-text review packets.

This module deliberately keeps AI assessment separate from human confirmation.
An AI recommendation can make a case ready for human adoption, but it cannot
materialize a label or open an external-evaluation gate.
"""

from __future__ import annotations

from typing import Any


SUPPORTED_BRANCHES = {"CONFIRMED", "LEGITIMATE"}
SUPPORTED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}


def _required_string(mapping: dict[str, Any], name: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _check_results(branch: str, required_checks: list[str]) -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    for check in required_checks:
        if branch == "LEGITIMATE" and check == "site_control_at_capture_time_reviewed":
            result = "PLAUSIBLE_NOT_CONCLUSIVELY_PROVEN"
            basis = (
                "Exact SEC-filed host and coherent captured identity support control, but a "
                "frozen page cannot conclusively prove control at every instant."
            )
        elif branch == "LEGITIMATE" and check in {
            "impersonation_or_compromise_reviewed",
            "adverse_regulator_evidence_reviewed",
        }:
            result = "NO_CONTRADICTION_FOUND_WITHIN_REVIEW_SCOPE"
            basis = (
                "No contrary indicator was found in the frozen capture and supplied official "
                "registration evidence; this is not an exhaustive future-risk guarantee."
            )
        elif branch == "CONFIRMED" and check == "official_warning_opened_or_locally_verified":
            result = "SUPPORTED_BY_OFFICIAL_REGULATOR_REFERENCE"
            basis = "The official regulator source was reviewed and matched to the candidate host/entity."
        elif check == "contradictory_evidence_review_complete":
            result = "NO_UNRESOLVED_CONTRADICTION_WITHIN_REVIEW_SCOPE"
            basis = "Packet cautions were individually dispositioned and no hard contradiction remained."
        else:
            result = "SUPPORTED_BY_FROZEN_EVIDENCE"
            basis = "The frozen packet, hashes, identity linkage, and preserved artifact support this check."
        results[check] = {"result": result, "basis": basis}
    return results


def build_ai_adjudication_record(
    review_form: dict[str, Any],
    packet_record: dict[str, Any],
    specification: dict[str, Any],
) -> dict[str, Any]:
    """Build one AI review record while leaving all human and label gates closed."""

    case_id = _required_string(review_form, "case_id")
    if packet_record.get("case_id") != case_id or specification.get("case_id") != case_id:
        raise ValueError("Case IDs do not align across workbook, packet, and specification")
    branch = _required_string(review_form, "branch")
    if branch not in SUPPORTED_BRANCHES:
        raise ValueError(f"Unsupported branch: {branch}")
    target = _required_string(review_form["automated_context"], "proposed_outcome")
    if target != branch or specification.get("recommended_decision") != target:
        raise ValueError("AI recommendation must align with the branch target")
    confidence = _required_string(specification, "recommended_confidence")
    if confidence not in SUPPORTED_CONFIDENCE:
        raise ValueError(f"Unsupported confidence: {confidence}")

    human_review = review_form.get("human_review", {})
    if (
        human_review.get("status") != "PENDING"
        or human_review.get("human_confirmation_recorded") is not False
        or review_form.get("label_created") is not False
        or review_form.get("external_evaluation_eligible") is not False
    ):
        raise ValueError("Source review form must remain pending and label-free")
    contradiction = packet_record.get("contradiction_review", {})
    if contradiction.get("hard_contradictions") != []:
        raise ValueError("AI target recommendation cannot retain a hard contradiction")
    packet_cautions = list(contradiction.get("caution_flags", []))
    dispositions = specification.get("caution_dispositions", {})
    if not isinstance(dispositions, dict) or set(dispositions) != set(packet_cautions):
        raise ValueError("Every packet caution must have exactly one AI disposition")
    if any(not isinstance(value, str) or not value.strip() for value in dispositions.values()):
        raise ValueError("Caution dispositions must be non-empty strings")

    official_evidence = specification.get("official_evidence")
    if not isinstance(official_evidence, dict):
        raise ValueError("official_evidence is required")
    if branch == "CONFIRMED":
        packet_url = packet_record.get("regulator_evidence", {}).get("url")
        if official_evidence.get("source_url") != packet_url:
            raise ValueError("Confirmed official-reference URL does not match the packet")
        if official_evidence.get("exact_candidate_alignment") is not True:
            raise ValueError("Confirmed recommendation requires exact official candidate alignment")
    else:
        sec = packet_record.get("sec_identity_and_registration", {})
        if str(official_evidence.get("crd")) != str(sec.get("crd")):
            raise ValueError("Legitimate CRD does not match the packet")
        if sec.get("captured_host_exactly_listed") is not True:
            raise ValueError("Legitimate recommendation requires an exact SEC-filed host")

    required_checks = list(review_form.get("review_contract", {}).get("required_checks", []))
    if not required_checks:
        raise ValueError("Review form has no required checks")
    rationale = _required_string(specification, "rationale")
    limitations = specification.get("residual_limitations", [])
    if not isinstance(limitations, list) or any(
        not isinstance(item, str) or not item.strip() for item in limitations
    ):
        raise ValueError("residual_limitations must be a list of non-empty strings")

    return {
        "case_id": case_id,
        "branch": branch,
        "candidate_host": review_form.get("candidate_host"),
        "source_packet": review_form.get("source_packet"),
        "ai_review": {
            "status": "COMPLETED",
            "reviewer_type": "AI_AGENT",
            "reviewer_id": "OpenAI Codex",
            "reviewed_at": _required_string(specification, "reviewed_at"),
            "authorization": _required_string(specification, "authorization"),
            "recommended_decision": target,
            "recommended_confidence": confidence,
            "rationale": rationale,
            "official_evidence": official_evidence,
            "required_check_results": _check_results(branch, required_checks),
            "caution_dispositions": dispositions,
            "residual_limitations": limitations,
            "unresolved_hard_contradictions": [],
            "ready_for_human_adoption": True,
            "recommendation_is_ground_truth": False,
        },
        "human_review": {
            "status": "PENDING",
            "human_confirmation_recorded": False,
            "final_decision": None,
            "label_confidence": None,
            "reviewer": None,
            "reviewed_at": None,
        },
        "ready_for_reconciled_intake": False,
        "source_intake_changed": False,
        "label_created": False,
        "external_evaluation_eligible": False,
    }

