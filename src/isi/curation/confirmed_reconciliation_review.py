"""Deterministic second-pass review helpers for confirmed-candidate drafts.

The helpers in this module only profile preserved candidate-page text and the
already-frozen first-pass metadata.  They never promote a draft to ground truth.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urlparse


SIGNAL_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "investment_or_trading_offering": (
        re.compile(
            r"\b(?:invest(?:ment|ing|or|ors)?|trad(?:e|er|ers|ing)|forex|"
            r"crypto(?:currency|currencies)?|cfds?|stocks?|shares?|commodit(?:y|ies)|"
            r"financial products?|investment plans?|loans?)\b",
            re.IGNORECASE,
        ),
    ),
    "account_or_action_call": (
        re.compile(
            r"\b(?:sign up|register(?: now)?|open (?:an? |cfd |prop |trading |funded )?account|"
            r"create (?:an? )?account|get started|start here|join now|invest with us|"
            r"apply (?:here|now)|request a call|deposit and invest|start trading|"
            r"upgrade to (?:a )?funded trading account)\b",
            re.IGNORECASE,
        ),
    ),
    "money_movement": (
        re.compile(
            r"\b(?:deposit(?:s|ed|ing)?|withdraw(?:al|als| funds?)?|initial deposit|"
            r"minimum deposit|wallet|payments?|funds?)\b",
            re.IGNORECASE,
        ),
    ),
    "return_or_performance_claim": (
        re.compile(
            r"\b(?:guarante(?:e|ed|es)|returns?|profit(?:s|able)?|yield|earnings?|"
            r"high income|passive income|performance)\b",
            re.IGNORECASE,
        ),
        re.compile(r"(?<!\w)\d{1,3}(?:\.\d+)?\s*%", re.IGNORECASE),
    ),
    "regulatory_or_safety_claim": (
        re.compile(
            r"\b(?:regulated|licensed|authori[sz]ed|compliant|registration|"
            r"licen[cs]e (?:number|no\.?|#)|bank-grade security|funds? (?:is|are) safe|"
            r"safe and secure|100% guaranteed)\b",
            re.IGNORECASE,
        ),
    ),
    "risk_disclosure": (
        re.compile(
            r"\b(?:risk warning|capital (?:is )?at risk|lose (?:some|all|money)|"
            r"loss(?:es)?|past performance|not guaranteed|cfds? are complex|high risk|"
            r"risk of ruin)\b",
            re.IGNORECASE,
        ),
    ),
}


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _bounded_context(text: str, start: int, end: int, radius: int = 90) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    prefix = "…" if left else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{text[left:right].strip()}{suffix}"


def profile_text_signals(text: str, max_contexts: int = 2) -> dict[str, dict[str, object]]:
    """Return bounded, auditable lexical signal profiles for preserved text."""

    normalized = _normalize_whitespace(text)
    output: dict[str, dict[str, object]] = {}
    for name, patterns in SIGNAL_PATTERNS.items():
        matches: list[re.Match[str]] = []
        for pattern in patterns:
            matches.extend(pattern.finditer(normalized))
        matches.sort(key=lambda item: (item.start(), item.end()))

        contexts: list[dict[str, str]] = []
        seen_contexts: set[str] = set()
        for match in matches:
            context = _bounded_context(normalized, match.start(), match.end())
            key = context.casefold()
            if key in seen_contexts:
                continue
            seen_contexts.add(key)
            contexts.append({"matched_text": match.group(0), "context": context})
            if len(contexts) >= max_contexts:
                break
        output[name] = {
            "detected": bool(matches),
            "match_count": len(matches),
            "bounded_contexts": contexts,
        }
    return output


def classify_warning(warning_categories: object, warning_url: str) -> dict[str, object]:
    """Classify frozen regulator metadata without reading the remote warning page."""

    category_value = ""
    category_detail = ""
    if isinstance(warning_categories, dict):
        category_value = str(warning_categories.get("category") or "")
        category_detail = str(warning_categories.get("detail") or "")
    category_codes = [item.strip() for item in category_value.split(",") if item.strip()]
    parsed_warning_url = urlparse(warning_url)
    warning_location = " ".join(
        (parsed_warning_url.path, parsed_warning_url.query, parsed_warning_url.fragment)
    )
    url_tokens = set(re.findall(r"[a-z0-9]+", warning_location.casefold()))
    explicit_impersonation_url = bool({"clone", "impersonation"} & url_tokens)

    if "5" in category_codes:
        evidence_class = "FRAUD_OR_MISCONDUCT_WARNING"
    elif "2" in category_codes or explicit_impersonation_url:
        evidence_class = "IMPERSONATION_OR_CLONE_WARNING"
    elif "1" in category_codes:
        evidence_class = "UNREGISTERED_OR_UNLICENSED_WARNING"
    else:
        evidence_class = "OFFICIAL_WARNING_UNCATEGORIZED"
    return {
        "category_codes": category_codes,
        "category_detail": category_detail or None,
        "explicit_impersonation_or_clone_in_url": explicit_impersonation_url,
        "evidence_class": evidence_class,
        "classification_is_ground_truth": False,
    }


def _date_from_value(value: object) -> date | None:
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


def assess_reconciliation_record(
    record: dict[str, object],
    first_pass: dict[str, object],
    *,
    raw_capture_hash_valid: bool,
    text_hash_valid: bool,
) -> dict[str, object]:
    """Build a non-mutating second-pass decision aid for one frozen draft."""

    artifact = record.get("artifact", {})
    text = str(artifact.get("text", ""))
    snapshot = first_pass.get("archive_snapshot", {})
    warning = first_pass.get("official_warning", {})
    comparison = first_pass.get("comparison", {})
    identity_check = snapshot.get("identity_token_check", {})
    signals = profile_text_signals(text)

    snapshot_date = _date_from_value(snapshot.get("snapshot_observed_at"))
    reference_date = _date_from_value(warning.get("validation_date"))
    days_before_reference = (
        (reference_date - snapshot_date).days
        if snapshot_date is not None and reference_date is not None
        else None
    )

    frozen_state_valid = (
        record.get("ground_truth_status") == "UNCERTAIN"
        and record.get("label_confidence") == "LOW"
        and record.get("review_status") == "IN_REVIEW"
        and all(item.get("reviewed") is False for item in record.get("evidence", []))
    )
    archive_host_match = snapshot.get("candidate_host_match") is True
    identity_full_match = identity_check.get("any_full_token_match") is True
    snapshot_not_after_reference = comparison.get("archive_snapshot_not_after_warning") is True
    warning_url = str(warning.get("url", ""))
    warning_reference_present = bool(
        warning_url.startswith("https://")
        and isinstance(warning.get("regulator"), dict)
        and warning.get("regulator", {}).get("name")
    )
    solicitation_supported = bool(
        signals["investment_or_trading_offering"]["detected"]
        and any(
            signals[name]["detected"]
            for name in (
                "account_or_action_call",
                "money_movement",
                "return_or_performance_claim",
            )
        )
    )

    gates = {
        "frozen_draft_state_valid": frozen_state_valid,
        "raw_capture_hash_valid": raw_capture_hash_valid,
        "normalized_text_hash_valid": text_hash_valid,
        "archive_replay_targets_candidate_host": archive_host_match,
        "candidate_identity_tokens_present": identity_full_match,
        "snapshot_not_after_reference_date": snapshot_not_after_reference,
        "official_warning_reference_present": warning_reference_present,
        "solicitation_supported_by_preserved_text": solicitation_supported,
    }
    hard_contradictions = [name for name, passed in gates.items() if not passed]

    caution_flags: list[str] = []
    local_capture = warning.get("local_capture_available") is True
    local_identity = warning.get("candidate_identity_visible_in_local_capture") is True
    if not local_capture:
        caution_flags.append("OFFICIAL_WARNING_NOT_LOCALLY_CAPTURED")
    elif not local_identity:
        caution_flags.append("LOCAL_WARNING_CAPTURE_DOES_NOT_EXPOSE_CANDIDATE_IDENTITY")
    if days_before_reference is not None and days_before_reference > 365:
        caution_flags.append("ARCHIVE_TO_REFERENCE_GAP_EXCEEDS_365_DAYS")
    if signals["regulatory_or_safety_claim"]["detected"]:
        caution_flags.append("CANDIDATE_PAGE_SELF_ASSERTS_REGULATION_LICENSE_OR_SAFETY")
    if (
        signals["return_or_performance_claim"]["detected"]
        and not signals["risk_disclosure"]["detected"]
    ):
        caution_flags.append("RETURN_OR_PERFORMANCE_CLAIM_WITHOUT_DETECTED_RISK_DISCLOSURE")

    warning_classification = classify_warning(warning.get("warning_categories"), warning_url)
    if not warning_classification["category_codes"]:
        caution_flags.append("WARNING_CATEGORY_CODE_MISSING")

    proposed_outcome = "CONFIRMED" if not hard_contradictions else "UNCERTAIN"
    if proposed_outcome == "CONFIRMED" and local_identity:
        confidence = "HIGH_FOR_HUMAN_REVIEW"
    elif proposed_outcome == "CONFIRMED":
        confidence = "MEDIUM_HIGH_FOR_HUMAN_REVIEW"
    else:
        confidence = "LOW_FOR_HUMAN_REVIEW"

    return {
        "case_id": record.get("case_id"),
        "candidate_id": first_pass.get("candidate_id"),
        "candidate_host": first_pass.get("candidate_host"),
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
        "identity_and_time_linkage": {
            "archive_snapshot_url": snapshot.get("url"),
            "archive_replay_targets_candidate_host": archive_host_match,
            "identity_token_check": identity_check,
            "snapshot_observed_date": snapshot_date.isoformat() if snapshot_date else None,
            "reference_validation_date": reference_date.isoformat() if reference_date else None,
            "days_snapshot_precedes_reference": days_before_reference,
            "snapshot_not_after_reference_date": snapshot_not_after_reference,
        },
        "regulator_evidence": {
            "url": warning_url,
            "regulator": warning.get("regulator"),
            "warning_classification": warning_classification,
            "local_capture_available": local_capture,
            "candidate_identity_visible_in_local_capture": local_identity,
            "warning_text_used_as_model_input": False,
        },
        "preserved_text_signal_profile": signals,
        "contradiction_review": {
            "automatic_gate_results": gates,
            "hard_contradictions": hard_contradictions,
            "caution_flags": caution_flags,
            "hard_contradiction_count": len(hard_contradictions),
            "caution_flag_count": len(caution_flags),
            "caution_flags_are_not_automatic_contradictions": True,
        },
        "automated_second_pass": {
            "proposed_outcome_for_human_review": proposed_outcome,
            "recommendation_confidence": confidence,
            "recommendation_is_ground_truth": False,
            "all_automatic_gates_pass": not hard_contradictions,
            "rationale": (
                "The preserved snapshot, candidate identity, reference timing, official warning metadata, "
                "and solicitation signals align without an automatic hard contradiction."
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
            "eligible_for_external_evaluation": False,
        },
        "external_evaluation_eligible": False,
    }
