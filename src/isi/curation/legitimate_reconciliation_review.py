"""Deterministic second-pass review helpers for legitimate-candidate drafts."""

from __future__ import annotations

from datetime import date, datetime

from src.isi.curation.confirmed_reconciliation_review import profile_text_signals


def _as_date(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None


def assess_legitimate_reconciliation_record(
    record: dict[str, object],
    first_pass: dict[str, object],
    *,
    raw_capture_hash_valid: bool,
    text_hash_valid: bool,
) -> dict[str, object]:
    """Build a non-mutating second-pass decision aid for one SEC-linked draft."""

    artifact = record.get("artifact", {})
    text = str(artifact.get("text", ""))
    profile = first_pass.get("sec_profile", {})
    comparison = first_pass.get("comparison", {})
    first_recommendation = first_pass.get("ai_first_pass", {})
    identity_check = comparison.get("identity_token_check", {})
    contacts = comparison.get("contact_field_check", {})
    registration = profile.get("registration", {})
    signals = profile_text_signals(text)

    filing_date = _as_date(profile.get("filing", {}).get("Dt"))
    capture_date = _as_date(artifact.get("content_observed_at"))
    days_after_filing = (
        (capture_date - filing_date).days
        if filing_date is not None and capture_date is not None
        else None
    )
    source_crd_matches = str(artifact.get("source_record_id", "")) == str(
        profile.get("crd", "")
    )
    frozen_state_valid = (
        record.get("ground_truth_status") == "UNCERTAIN"
        and record.get("label_confidence") == "LOW"
        and record.get("review_status") == "IN_REVIEW"
        and all(item.get("reviewed") is False for item in record.get("evidence", []))
    )
    registered_and_approved = (
        registration.get("FirmType") == "Registered" and registration.get("St") == "APPROVED"
    )
    host_exact = comparison.get("host_exactly_listed_in_sec_filing") is True
    identity_full = identity_check.get("any_full_token_match") is True
    filing_not_after_capture = days_after_filing is not None and days_after_filing >= 0
    text_sufficient = len(text) >= 200
    first_pass_aligned = (
        first_recommendation.get("recommended_identity_relationship") == "SAME_ENTITY_LIKELY"
        and first_recommendation.get("recommended_evidence_assessment")
        == "REGISTRATION_RELEVANT"
        and first_recommendation.get("recommended_outcome_for_human_review") == "LEGITIMATE"
    )
    gates = {
        "frozen_draft_state_valid": frozen_state_valid,
        "raw_capture_hash_valid": raw_capture_hash_valid,
        "normalized_text_hash_valid": text_hash_valid,
        "artifact_source_crd_matches_sec_profile": source_crd_matches,
        "captured_host_exactly_listed_in_sec_filing": host_exact,
        "sec_registration_registered_and_approved": registered_and_approved,
        "firm_identity_tokens_present_in_capture": identity_full,
        "sec_filing_not_after_capture": filing_not_after_capture,
        "preserved_visible_text_at_least_200_characters": text_sufficient,
        "first_pass_identity_and_outcome_aligned": first_pass_aligned,
    }
    hard_contradictions = [name for name, passed in gates.items() if not passed]

    matched_contacts = int(contacts.get("matched_count", 0))
    available_contacts = int(contacts.get("available_count", 0))
    caution_flags: list[str] = []
    if matched_contacts == 0:
        caution_flags.append("NO_SEC_CONTACT_FIELD_MATCH_IN_CAPTURE")
    elif matched_contacts < 2:
        caution_flags.append("FEWER_THAN_TWO_SEC_CONTACT_FIELDS_MATCH_IN_CAPTURE")
    if len(text) < 500:
        caution_flags.append("SHORT_PRESERVED_VISIBLE_TEXT_UNDER_500_CHARACTERS")
    if signals["return_or_performance_claim"]["detected"]:
        caution_flags.append("RETURN_OR_PERFORMANCE_LANGUAGE_REQUIRES_CONTEXT_REVIEW")
    if signals["regulatory_or_safety_claim"]["detected"]:
        caution_flags.append("REGULATORY_OR_SAFETY_LANGUAGE_REQUIRES_CONTEXT_REVIEW")

    proposed_outcome = "LEGITIMATE" if not hard_contradictions else "UNCERTAIN"
    confidence = (
        "HIGH_FOR_HUMAN_REVIEW"
        if proposed_outcome == "LEGITIMATE" and matched_contacts >= 2 and len(text) >= 500
        else "MEDIUM_HIGH_FOR_HUMAN_REVIEW"
        if proposed_outcome == "LEGITIMATE"
        else "LOW_FOR_HUMAN_REVIEW"
    )
    return {
        "case_id": record.get("case_id"),
        "candidate_host": comparison.get("artifact_host"),
        "source_state": {
            "ground_truth_status": record.get("ground_truth_status"),
            "label_confidence": record.get("label_confidence"),
            "review_status": record.get("review_status"),
            "record_state_changed": False,
        },
        "source_integrity": {
            "raw_capture_path": artifact.get("source_capture_path"),
            "raw_capture_sha256": artifact.get("source_capture_sha256"),
            "raw_capture_hash_valid": raw_capture_hash_valid,
            "normalized_text_sha256": artifact.get("text_sha256"),
            "normalized_text_hash_valid": text_hash_valid,
            "visible_text_characters": len(text),
        },
        "sec_identity_and_registration": {
            "crd": profile.get("crd"),
            "sec_number": profile.get("sec_number"),
            "business_name": profile.get("business_name"),
            "legal_name": profile.get("legal_name"),
            "registration": registration,
            "filing": profile.get("filing"),
            "filed_web_hosts": profile.get("normalized_web_hosts"),
            "captured_host": comparison.get("artifact_host"),
            "captured_host_exactly_listed": host_exact,
            "identity_token_check": identity_check,
            "contact_field_check": contacts,
            "capture_observed_date": capture_date.isoformat() if capture_date else None,
            "filing_date": filing_date.isoformat() if filing_date else None,
            "days_capture_follows_filing": days_after_filing,
            "registration_is_identity_evidence_not_safety_endorsement": True,
        },
        "preserved_text_context_profile": signals,
        "contradiction_review": {
            "automatic_gate_results": gates,
            "hard_contradictions": hard_contradictions,
            "caution_flags": caution_flags,
            "hard_contradiction_count": len(hard_contradictions),
            "caution_flag_count": len(caution_flags),
            "caution_flags_are_not_automatic_contradictions": True,
            "unresolved_human_checks": [
                "Confirm the captured site was controlled by the SEC-listed firm at observation time.",
                "Check for impersonation, compromise, misleading claims, or adverse regulator evidence.",
                "Treat SEC registration as identity evidence, not as endorsement of every page claim.",
            ],
        },
        "automated_second_pass": {
            "proposed_outcome_for_human_review": proposed_outcome,
            "recommendation_confidence": confidence,
            "recommendation_is_ground_truth": False,
            "all_automatic_gates_pass": not hard_contradictions,
            "rationale": (
                "The preserved capture aligns with the SEC-filed host, CRD, firm identity, "
                "registered/approved state, and filing chronology without an automatic hard contradiction."
                if not hard_contradictions
                else "One or more automatic gates failed; keep the case UNCERTAIN until resolved."
            ),
        },
        "human_decision": {
            "decision": None,
            "final_confidence": None,
            "reviewer": None,
            "reviewed_at": None,
            "rationale": None,
            "contradictory_evidence_reviewed": None,
            "site_control_confirmed": None,
            "eligible_for_external_evaluation": False,
        },
        "external_evaluation_eligible": False,
    }
