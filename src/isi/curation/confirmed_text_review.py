"""Offline AI-assisted first-pass review for confirmed-candidate snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from src.isi.normalization.external_text import identity_token_check


def _snapshot_timestamp(archive_url: str) -> str | None:
    parts = urlparse(archive_url).path.split("/")
    if len(parts) < 3:
        return None
    raw = parts[2].removesuffix("id_")
    if len(raw) != 14 or not raw.isdigit():
        return None
    return raw


def assess_confirmed_record(
    record: dict[str, object],
    candidate: dict[str, object],
    warning_screen: dict[str, object] | None,
) -> dict[str, object]:
    artifact = record["artifact"]
    text = str(artifact["text"])
    host = str(candidate["candidate_host"])
    entity_keys = [str(value) for value in candidate.get("entity_name_keys", [])]
    identity = identity_token_check(entity_keys, text)
    archive_url = str(artifact["url"])
    archive_path = urlparse(archive_url).path
    archived_original_host = ""
    for prefix in ("/web/",):
        if archive_path.startswith(prefix):
            marker_index = archive_url.find("id_/")
            if marker_index >= 0:
                archived_original_host = (
                    urlparse(archive_url[marker_index + 4 :]).hostname or ""
                ).casefold().removeprefix("www.")
    archive_host_matches = archived_original_host == host.casefold().removeprefix("www.")

    snapshot_raw = _snapshot_timestamp(archive_url)
    warning_date_raw = str(
        candidate["official_reference"].get("evidence_dates", {}).get("validation_date", "")
    )
    snapshot_iso = None
    snapshot_not_after_warning = None
    if snapshot_raw:
        snapshot = datetime.strptime(snapshot_raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        snapshot_iso = snapshot.isoformat()
        try:
            warning_date = datetime.strptime(warning_date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            snapshot_not_after_warning = snapshot.date() <= warning_date.date()
        except ValueError:
            snapshot_not_after_warning = None

    official_capture_available = warning_screen is not None
    official_identity_visible = bool(
        warning_screen
        and (
            warning_screen.get("candidate_host_in_visible_text")
            or warning_screen.get("identity_check", {}).get("any_full_token_match")
        )
    )
    signals = []
    if archive_host_matches:
        signals.append("archive replay URL targets the candidate host")
    if identity["any_full_token_match"]:
        signals.append("candidate identity is present in archived visible text")
    if snapshot_not_after_warning:
        signals.append("archived observation predates or matches the regulator warning date")
    if official_identity_visible:
        signals.append("locally preserved official warning visibly names the candidate host or entity")

    if archive_host_matches and identity["any_full_token_match"]:
        relationship = "SAME_ENTITY_LIKELY"
        outcome = "CONFIRMED"
    else:
        relationship = "UNRESOLVED"
        outcome = "UNCERTAIN"
    confidence = "HIGH" if official_identity_visible and outcome == "CONFIRMED" else "MEDIUM_HIGH"
    if outcome != "CONFIRMED":
        confidence = "LOW"

    return {
        "case_id": record["case_id"],
        "candidate_id": candidate["candidate_id"],
        "candidate_host": host,
        "archive_snapshot": {
            "url": archive_url,
            "snapshot_observed_at": snapshot_iso,
            "archive_original_host": archived_original_host,
            "candidate_host_match": archive_host_matches,
            "text_sha256": artifact["text_sha256"],
            "source_capture_path": artifact["source_capture_path"],
            "source_capture_sha256": artifact["source_capture_sha256"],
            "visible_text_characters": len(text),
            "identity_token_check": identity,
            "bounded_excerpt": text[:600],
        },
        "official_warning": {
            "url": candidate["official_reference"]["url"],
            "regulator": candidate["official_reference"]["regulator"],
            "warning_categories": candidate["official_reference"].get("warning_categories"),
            "validation_date": warning_date_raw,
            "local_capture_available": official_capture_available,
            "candidate_identity_visible_in_local_capture": official_identity_visible,
            "warning_text_as_model_input_allowed": False,
        },
        "comparison": {
            "archive_snapshot_not_after_warning": snapshot_not_after_warning,
            "decisive_signals": signals,
        },
        "ai_first_pass": {
            "recommended_identity_relationship": relationship,
            "recommended_evidence_assessment": "REGULATOR_WARNING_RELEVANT",
            "recommended_outcome_for_human_review": outcome,
            "recommendation_confidence": confidence,
            "recommendation_is_ground_truth": False,
            "rationale": (
                "The archived model-input candidate and the regulator reference align on host/identity. "
                "This supports a bounded human review recommendation only; it does not mutate the intake "
                "record or create a ground-truth label."
            ),
        },
        "human_review_required": [
            "Confirm the archived page is the warned entity's solicitation rather than unrelated or injected content.",
            "Confirm the official warning applies to this exact host/entity and inspect any contradictory evidence.",
            "Confirm the warning evidence is sufficient for the project definition of CONFIRMED.",
            "Only then decide whether to set CONFIRMED + HIGH + RECONCILED.",
        ],
        "record_state_changed": False,
        "external_evaluation_eligible": False,
    }
