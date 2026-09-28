"""Offline normalization helpers for provenance-preserving HTML captures."""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


SKIPPED_TAGS = {"script", "style", "noscript", "svg", "template"}
LEGAL_SUFFIXES = {
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "llp",
    "lp",
    "ltd",
    "plc",
}


class VisibleHTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.chunks: list[str] = []
        self.canonical_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in SKIPPED_TAGS:
            self._skip_depth += 1
        if lowered != "link":
            return
        values = {key.lower(): value for key, value in attrs if value is not None}
        relations = {part.casefold() for part in values.get("rel", "").split()}
        href = values.get("href")
        if "canonical" in relations and href:
            self.canonical_urls.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.chunks.append(data)


def extract_visible_text(html_bytes: bytes) -> tuple[str, list[str]]:
    """Return normalized visible text and declared canonical URLs.

    Exact repeated text nodes of at least 40 characters are collapsed. This
    removes duplicate desktop/mobile blocks while preserving the immutable HTML
    capture and short repeated navigation labels for auditability.
    """

    html = html_bytes.decode("utf-8", errors="replace")
    parser = VisibleHTMLTextParser()
    parser.feed(html)
    normalized_chunks = []
    seen_long_chunks: set[str] = set()
    for raw_chunk in parser.chunks:
        chunk = re.sub(r"\s+", " ", raw_chunk).strip()
        if not chunk:
            continue
        if len(chunk) >= 40:
            if chunk in seen_long_chunks:
                continue
            seen_long_chunks.add(chunk)
        normalized_chunks.append(chunk)
    text = re.sub(r"\s+", " ", " ".join(normalized_chunks)).strip()
    canonical = list(dict.fromkeys(parser.canonical_urls))
    return text, canonical


def normalize_identity(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def identity_token_check(entity_keys: list[str], text: str) -> dict[str, object]:
    """Conservative lexical identity check; this is not entity resolution."""

    normalized_text = normalize_identity(text)
    text_tokens = set(normalized_text.split())
    candidates = []
    for entity in entity_keys:
        normalized_entity = normalize_identity(entity)
        tokens = [
            token
            for token in normalized_entity.split()
            if token not in LEGAL_SUFFIXES and len(token) >= 3
        ]
        if not tokens:
            continue
        matched = [token for token in tokens if token in text_tokens]
        candidates.append(
            {
                "entity_key": entity,
                "identity_tokens": tokens,
                "matched_tokens": matched,
                "all_identity_tokens_present": len(matched) == len(tokens),
            }
        )
    return {
        "candidate_checks": candidates,
        "any_full_token_match": any(item["all_identity_tokens_present"] for item in candidates),
        "interpretation": "Lexical first pass only; human identity reconciliation is still required.",
    }


def choose_capture_url(candidate_host: str, canonical_urls: list[str]) -> str:
    allowed_hosts = {candidate_host.casefold(), f"www.{candidate_host.casefold()}"}
    for value in canonical_urls:
        parsed = urlparse(value)
        if parsed.scheme == "https" and (parsed.hostname or "").casefold() in allowed_hosts:
            return value
    return f"https://{candidate_host}/"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def capture_to_draft_record(
    *,
    candidate: dict[str, object],
    capture_path: Path,
    capture_relative_path: str,
    content_observed_at: str,
    collection_date: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw = capture_path.read_bytes()
    text, canonical_urls = extract_visible_text(raw)
    candidate_id = str(candidate["candidate_id"])
    host = str(candidate["candidate_host"])
    entity_keys = [str(value) for value in candidate.get("entity_name_keys", [])]
    identity_check = identity_token_check(entity_keys, text)
    capture_url = choose_capture_url(host, canonical_urls)
    text_hash = sha256_bytes(text.encode("utf-8"))
    capture_hash = sha256_bytes(raw)
    source_record_id = str(candidate["source_record_id"])
    source_id = "sec_iapd_homepage_capture_2026_09_24"
    suffix = candidate_id.removeprefix("EXTCAP_")
    record = {
        "case_id": f"CASE_{suffix}",
        "ground_truth_status": "UNCERTAIN",
        "label_confidence": "LOW",
        "review_status": "IN_REVIEW",
        "review_rationale": (
            "Automatic draft from a raw homepage capture on the host recorded by SEC/IAPD. "
            "Identity, control of the host, and content legitimacy have not been human-reconciled."
        ),
        "case_or_campaign_group_id": f"CASEGRP_{suffix}",
        "near_duplicate_group_id": f"NDG_{suffix}",
        "artifact": {
            "artifact_id": f"ART_{suffix}",
            "source_id": source_id,
            "source_record_id": source_record_id,
            "artifact_type": "WEBSITE_SNAPSHOT",
            "text": text,
            "text_sha256": text_hash,
            "language": "en",
            "url": capture_url,
            "collection_date": collection_date,
            "content_observed_at": content_observed_at,
            "source_capture_path": capture_relative_path.replace("\\", "/"),
            "source_capture_sha256": capture_hash,
        },
        "evidence": [
            {
                "evidence_id": f"EVD_{suffix}_SEC",
                "evidence_type": "official_registry",
                "source_id": "sec_iapd",
                "source_url": candidate["official_reference"]["url"],
                "summary": (
                    "SEC/IAPD reference links the named registered firm to this candidate host. "
                    "It supports an identity review only and is not a content-safety label."
                ),
                "supports": ["IDENTITY"],
                "reviewed": False,
            }
        ],
    }
    profile = {
        "candidate_id": candidate_id,
        "candidate_host": host,
        "capture_path": str(capture_path),
        "capture_sha256": capture_hash,
        "capture_bytes": len(raw),
        "capture_url": capture_url,
        "canonical_urls": canonical_urls,
        "visible_text_characters": len(text),
        "non_whitespace_text_characters": len(re.sub(r"\s+", "", text)),
        "text_sha256": text_hash,
        "identity_check": identity_check,
        "ground_truth_status": "UNCERTAIN",
        "external_evaluation_eligible": False,
    }
    return record, profile
