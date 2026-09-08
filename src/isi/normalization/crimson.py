"""Normalize Crimson records into URL artifacts without network access."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


SOURCE_ID = "crimson_www_2025"
SOURCE_LABEL = "research_detected_crypto_investment_scam_website"
SOURCE_LABEL_SEMANTICS = (
    "Research-detected cryptocurrency investment-scam website; "
    "not a legal finding and not a thesis ground-truth label."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_url(value: object) -> tuple[str, str, bool] | None:
    """Return a URI-safe URL/domain; add a marker when raw data held only a hostname.

    Crimson stores its URL field as a hostname. The original value remains immutable
    in raw data; the synthetic ``https://`` prefix below is only a schema-safe
    canonical representation and must never cause a fetch.
    """
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url or any(character.isspace() for character in url):
        return None
    has_scheme = url.lower().startswith(("http://", "https://"))
    parsed = urlsplit(url if has_scheme else f"https://{url}")
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        return None
    if "." not in parsed.hostname:
        return None
    return parsed.geturl(), parsed.hostname.lower(), not has_scheme


def normalize_records(
    input_path: Path, output_path: Path, collection_date: date
) -> dict[str, object]:
    """Create candidate URL artifacts. Invalid records are counted, not silently used."""
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Crimson data.json must contain a top-level JSON list")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    invalid = 0
    bare_domain = 0
    domains: Counter[str] = Counter()
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise ValueError(f"Crimson record {index} is not an object")
            normalized = normalize_url(record.get("url"))
            if normalized is None:
                invalid += 1
                continue
            url, domain, was_bare_domain = normalized
            bare_domain += int(was_bare_domain)
            domains[domain] += 1
            artifact = {
                "artifact_id": f"ART_CRIMSON_{index:06d}",
                "case_id": None,
                "source_id": SOURCE_ID,
                "source_record_id": str(index),
                "artifact_type": "URL",
                "source_label": SOURCE_LABEL,
                "source_label_semantics": SOURCE_LABEL_SEMANTICS,
                "text": None,
                "language": None,
                "url": url,
                "domain": domain,
                "image_path": None,
                "has_text": False,
                "has_image": False,
                "has_url": True,
                "collection_date": collection_date.isoformat(),
                "content_observed_at": None,
                "near_duplicate_group_id": f"DOMAIN_{domain.upper().replace('.', '_').replace('-', '_')}"
                if domain
                else None,
            }
            output.write(json.dumps(artifact, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {
        "input_sha256": sha256_file(input_path),
        "input_record_count": len(records),
        "candidate_artifact_count": len(records) - invalid,
        "invalid_url_count": invalid,
        "bare_domain_canonicalized_count": bare_domain,
        "unique_domain_count": len(domains),
        "output_sha256": sha256_file(output_path),
        "network_policy": "No listed URL was requested during normalization.",
        "canonicalization_policy": "For raw hostname-only values, url is rendered as https://<hostname> solely for URI-schema compatibility; raw values remain in the immutable source file.",
    }
