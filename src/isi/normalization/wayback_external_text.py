"""Offline preparation helpers for Internet Archive HTML captures."""

from __future__ import annotations

import gzip
import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path

from src.isi.normalization.external_text import extract_visible_text, identity_token_check


MAX_DECOMPRESSED_BYTES = 25 * 1024 * 1024
PARKING_MARKERS = {
    "buy this domain",
    "domain is for sale",
    "namecheap",
    "parkingcrew",
    "sedo domain parking",
    "this domain may be for sale",
}
SOLICITATION_MARKERS = {
    "account",
    "capital",
    "copy trading",
    "deposit",
    "earn",
    "financial",
    "forex",
    "funded account",
    "investment",
    "investor",
    "market",
    "passive profit",
    "portfolio",
    "profit",
    "return",
    "trade",
    "trader",
    "trading",
    "wealth",
    "withdraw",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def decode_archived_payload(raw: bytes) -> tuple[bytes, str]:
    """Decode transport compression without modifying the immutable raw capture."""

    if not raw.startswith(b"\x1f\x8b"):
        return raw, "identity"
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as handle:
        decoded = handle.read(MAX_DECOMPRESSED_BYTES + 1)
    if len(decoded) > MAX_DECOMPRESSED_BYTES:
        raise ValueError("Archived payload exceeds the decompressed-size safety limit")
    return decoded, "gzip"


def screen_archived_capture(
    *, candidate: dict[str, object], capture_path: Path
) -> tuple[dict[str, object], str, list[str]]:
    """Screen a local archive capture for identity and content relevance.

    The outcome is a curation routing decision, never a ground-truth label.
    """

    raw = capture_path.read_bytes()
    decoded, transport_decoding = decode_archived_payload(raw)
    text, canonical_urls = extract_visible_text(decoded)
    entity_keys = [str(value) for value in candidate.get("entity_name_keys", [])]
    identity = identity_token_check(entity_keys, text)
    normalized = re.sub(r"\s+", " ", text.casefold())
    parking_hits = sorted(marker for marker in PARKING_MARKERS if marker in normalized)
    solicitation_hits = sorted(marker for marker in SOLICITATION_MARKERS if marker in normalized)
    non_whitespace = len(re.sub(r"\s+", "", text))

    if parking_hits:
        decision = "REJECT_PARKED_DOMAIN"
        reasons = ["parking_or_domain_sale_content_detected"]
    elif not identity["any_full_token_match"]:
        decision = "REJECT_IDENTITY_MISMATCH_OR_REPURPOSED_DOMAIN"
        reasons = ["candidate_identity_not_present_in_archived_visible_text"]
    elif non_whitespace < 200:
        decision = "REJECT_INSUFFICIENT_VISIBLE_TEXT"
        reasons = ["archived_visible_text_below_review_threshold"]
    elif len(solicitation_hits) < 2:
        decision = "REJECT_NO_INVESTMENT_SOLICITATION_SIGNAL"
        reasons = ["fewer_than_two_conservative_investment_or_solicitation_markers"]
    else:
        decision = "REVIEWABLE_OBSERVED_TEXT"
        reasons = [
            "candidate_identity_present",
            "sufficient_visible_text",
            "investment_or_solicitation_markers_present",
        ]

    profile = {
        "candidate_id": candidate.get("candidate_id"),
        "candidate_host": candidate.get("candidate_host"),
        "capture_path": str(capture_path),
        "capture_bytes": len(raw),
        "capture_sha256": sha256_bytes(raw),
        "transport_decoding": transport_decoding,
        "decoded_bytes": len(decoded),
        "decoded_sha256": sha256_bytes(decoded),
        "visible_text_characters": len(text),
        "non_whitespace_text_characters": non_whitespace,
        "text_sha256": sha256_bytes(text.encode("utf-8")),
        "canonical_urls": canonical_urls,
        "identity_check": identity,
        "parking_marker_hits": parking_hits,
        "solicitation_marker_hits": solicitation_hits,
        "screening_decision": decision,
        "screening_reasons": reasons,
        "ground_truth_status": "UNCERTAIN",
        "label_created": False,
        "external_evaluation_eligible": False,
    }
    return profile, text, canonical_urls


def snapshot_timestamp_iso(value: str) -> str:
    parsed = datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def archived_capture_to_draft_record(
    *,
    candidate: dict[str, object],
    capture_item: dict[str, object],
    capture_path: Path,
    capture_relative_path: str,
    collection_date: str,
    profile: dict[str, object],
    text: str,
) -> dict[str, object]:
    """Create an explicitly unlabeled, non-eligible human-review draft."""

    candidate_id = str(candidate["candidate_id"])
    suffix = candidate_id.removeprefix("EXTCAP_")
    archive_url = str(capture_item.get("final_archive_url") or capture_item["requested_archive_url"])
    return {
        "case_id": f"CASE_{suffix}",
        "ground_truth_status": "UNCERTAIN",
        "label_confidence": "LOW",
        "review_status": "IN_REVIEW",
        "review_rationale": (
            "Offline draft from an Internet Archive snapshot. Automated screening found candidate identity "
            "and investment-related observed text, but a human has not reconciled the artifact with the "
            "official warning. It is not eligible for evaluation or training."
        ),
        "case_or_campaign_group_id": f"CASEGRP_{suffix}",
        "near_duplicate_group_id": f"NDG_{suffix}",
        "artifact": {
            "artifact_id": f"ART_{suffix}",
            "source_id": "wayback_confirmed_capture_2026_09_24",
            "source_record_id": str(candidate["source_record_id"]),
            "artifact_type": "WEBSITE_SNAPSHOT",
            "text": text,
            "text_sha256": profile["text_sha256"],
            "language": "en",
            "url": archive_url,
            "collection_date": collection_date,
            "content_observed_at": snapshot_timestamp_iso(str(capture_item["snapshot_timestamp"])),
            "source_capture_path": capture_relative_path.replace("\\", "/"),
            "source_capture_sha256": profile["capture_sha256"],
        },
        "evidence": [
            {
                "evidence_id": f"EVD_{suffix}_REGULATOR",
                "evidence_type": "regulator_warning",
                "source_id": str(candidate["source_id"]),
                "source_url": candidate["official_reference"]["url"],
                "summary": (
                    "The official regulator reference names the candidate entity or host. It is evidence "
                    "for human review, not model-input text and not an automatic label."
                ),
                "supports": ["SCAM_CLAIM", "DOMAIN_LINK"],
                "reviewed": False,
            },
            {
                "evidence_id": f"EVD_{suffix}_ARCHIVE",
                "evidence_type": "web_snapshot",
                "source_id": "internet_archive",
                "source_url": archive_url,
                "summary": (
                    "The archived snapshot preserves observed text associated with the candidate host. "
                    "It supports identity/domain reconciliation only and does not establish ground truth."
                ),
                "supports": ["IDENTITY", "DOMAIN_LINK"],
                "reviewed": False,
            },
        ],
    }
