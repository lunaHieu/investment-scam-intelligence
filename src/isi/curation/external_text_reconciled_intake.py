"""Materialize human-adopted AI recommendations into a separate intake batch."""

from __future__ import annotations

import copy
from typing import Any


def materialize_reconciled_record(
    source_record: dict[str, Any],
    ai_record: dict[str, Any],
    adoption: dict[str, Any],
) -> dict[str, Any]:
    """Return a reconciled copy while preserving the frozen source record."""

    if adoption.get("accepted_all_ai_recommendations") is not True:
        raise ValueError("Explicit adoption of AI recommendations is required")
    if adoption.get("independent_human_evidence_rereview_claimed") is not False:
        raise ValueError("This workflow must not claim an independent human rereview")
    case_id = source_record.get("case_id")
    if not case_id or ai_record.get("case_id") != case_id:
        raise ValueError("Source and AI case IDs do not align")
    if (
        source_record.get("ground_truth_status") != "UNCERTAIN"
        or source_record.get("label_confidence") != "LOW"
        or source_record.get("review_status") != "IN_REVIEW"
    ):
        raise ValueError("Source record is not a frozen in-review draft")
    ai = ai_record.get("ai_review", {})
    if (
        ai.get("status") != "COMPLETED"
        or ai.get("reviewer_type") != "AI_AGENT"
        or ai.get("ready_for_human_adoption") is not True
        or ai.get("recommended_confidence") != "HIGH"
        or ai.get("unresolved_hard_contradictions") != []
    ):
        raise ValueError("AI adjudication is not eligible for adoption")
    decision = ai.get("recommended_decision")
    if decision not in {"CONFIRMED", "LEGITIMATE"} or ai_record.get("branch") != decision:
        raise ValueError("AI decision and branch do not align")

    output = copy.deepcopy(source_record)
    output["ground_truth_status"] = decision
    output["label_confidence"] = "HIGH"
    output["review_status"] = "RECONCILED"
    output["review_rationale"] = (
        "The project owner authorized progression after the completed AI manual adjudication. "
        "The recommendation was adopted without claiming an independent human evidence rereview. "
        + str(ai.get("rationale", "")).strip()
    )
    evidence = output.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Source record has no evidence")
    if decision == "CONFIRMED":
        strong = [item for item in evidence if item.get("evidence_type") == "regulator_warning"]
        official_url = ai.get("official_evidence", {}).get("source_url")
        if len(strong) != 1 or strong[0].get("source_url") != official_url:
            raise ValueError("Confirmed regulator evidence does not match the AI review")
        if "SCAM_CLAIM" not in strong[0].get("supports", []):
            raise ValueError("Confirmed regulator evidence lacks SCAM_CLAIM support")
    else:
        strong = [item for item in evidence if item.get("evidence_type") == "official_registry"]
        crd = str(ai.get("official_evidence", {}).get("crd", ""))
        if len(strong) != 1 or not str(strong[0].get("source_url", "")).rstrip("/").endswith(
            f"/{crd}"
        ):
            raise ValueError("Legitimate registry evidence does not match the AI review")
        supports = list(strong[0].get("supports", []))
        if "LEGITIMACY" not in supports:
            supports.append("LEGITIMACY")
        strong[0]["supports"] = supports
    for item in evidence:
        item["reviewed"] = True
        item["review_provenance"] = "AI_MANUAL_REVIEW_HUMAN_OWNER_ADOPTED"

    output["review_provenance"] = {
        "adoption_id": adoption.get("adoption_id"),
        "adopted_at": adoption.get("adopted_at"),
        "adopter_role": adoption.get("adopter_role"),
        "authorization_source": adoption.get("authorization_source"),
        "ai_adjudication_analysis_id": adoption.get("scope", {}).get(
            "ai_adjudication_analysis_id"
        ),
        "ai_reviewer": ai.get("reviewer_id"),
        "independent_human_evidence_rereview": False,
        "hard_contradictions_remaining": 0,
    }
    output["external_evaluation_eligible"] = True
    return output

