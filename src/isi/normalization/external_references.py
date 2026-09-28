"""Build deterministic, offline lookup indices from pinned public references.

The output is deliberately unsuitable as a training label.  IOSCO records are
warning evidence, while SEC/IAPD records are registration references.  Neither
source establishes the truth of arbitrary content or the identity of a website
operator.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import ipaddress
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


INDEX_SCHEMA_VERSION = "external_reference_index_v1"
IOSCO_NAME_FIELDS = ("commercial_name", "other_commercial_names", "corporate_names")
IOSCO_HOST_FIELDS = ("url", "other_urls", "domain_name", "fqdn")
MULTIVALUE_SEPARATOR = re.compile(r"[\r\n|;]+")
EXPLICIT_URL = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s|;,]+")
BARE_HOST = re.compile(
    r"(?i)(?<![@a-z0-9._-])(?:www\.)?"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,62})\.)+"
    r"(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})"
    r"(?::\d+)?(?=$|[^a-z0-9._-])"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def split_multivalue(value: str | None) -> list[str]:
    """Split only on explicit list separators, not commas inside entity names/URLs."""

    if not value:
        return []
    return [part.strip() for part in MULTIVALUE_SEPARATOR.split(value) if part.strip()]


def normalize_entity_name(value: str | None) -> str | None:
    """Return a conservative Unicode-aware name key, or None for unsafe input."""

    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or "\ufffd" in normalized:
        return None
    characters = [character.casefold() if character.isalnum() else " " for character in normalized]
    key = " ".join("".join(characters).split())
    return key or None


def canonicalize_host(value: str | None) -> str | None:
    """Extract a lowercase ASCII host without making network or public-suffix claims."""

    if not value:
        return None
    candidate = unicodedata.normalize("NFKC", value).strip().strip("'\"<>()[]{}.,")
    if not candidate or "\ufffd" in candidate or any(char.isspace() for char in candidate):
        return None
    if "@" in candidate and "://" not in candidate:
        return None
    try:
        parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
        host = parsed.hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.rstrip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    labels = ascii_host.split(".")
    if len(labels) < 2 or any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not re.fullmatch(r"[a-z0-9-]+", label)
        for label in labels
    ):
        return None
    return ascii_host


def extract_hosts(values: list[str]) -> list[str]:
    hosts: set[str] = set()
    for value in values:
        if host := canonicalize_host(value):
            hosts.add(host)
        explicit_matches = list(EXPLICIT_URL.finditer(value))
        for match in explicit_matches:
            if host := canonicalize_host(match.group(0)):
                hosts.add(host)
        # Remove full explicit URLs before scanning for bare hosts. This avoids
        # mistaking dotted application IDs or query values for hostnames.
        remainder = EXPLICIT_URL.sub(" ", value)
        for match in BARE_HOST.finditer(remainder):
            if host := canonicalize_host(match.group(0)):
                hosts.add(host)
    return sorted(hosts)


def _collision_summary(index: dict[str, set[str]]) -> dict[str, int]:
    collisions = [record_ids for record_ids in index.values() if len(record_ids) > 1]
    return {
        "unique_key_count": len(index),
        "keys_shared_by_multiple_records": len(collisions),
        "records_in_shared_key_groups": sum(len(record_ids) for record_ids in collisions),
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def build_iosco_index(
    raw_path: Path,
    output_path: Path,
    *,
    source_version: str,
    raw_sha256: str,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    entity_index: dict[str, set[str]] = {}
    host_index: dict[str, set[str]] = {}
    quality_counts: Counter[str] = Counter()

    with raw_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"id", "commercial_name", "nca_name", "nca_jurisdiction"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"IOSCO CSV is missing required columns: {sorted(missing)}")
        for row_number, row in enumerate(reader, start=1):
            record_id = (row.get("id") or "").strip() or f"ROW_{row_number:08d}"
            name_values = [part for field in IOSCO_NAME_FIELDS for part in split_multivalue(row.get(field))]
            entity_keys = sorted({key for value in name_values if (key := normalize_entity_name(value))})
            rejected_names = sum(normalize_entity_name(value) is None for value in name_values)
            host_values = [part for field in IOSCO_HOST_FIELDS for part in split_multivalue(row.get(field))]
            hosts = extract_hosts(host_values)
            quality_flags: list[str] = []
            if rejected_names:
                quality_flags.append("ENTITY_NAME_REJECTED_DURING_NORMALIZATION")
                quality_counts["records_with_rejected_entity_name"] += 1
            if not entity_keys:
                quality_flags.append("NO_USABLE_ENTITY_NAME_KEY")
                quality_counts["records_without_entity_name_key"] += 1
            if not hosts:
                quality_flags.append("NO_USABLE_OBSERVED_HOST")
                quality_counts["records_without_observed_host"] += 1

            record = {
                "schema_version": INDEX_SCHEMA_VERSION,
                "source_id": "iosco_i_scan",
                "source_version": source_version,
                "source_raw_sha256": raw_sha256,
                "source_record_id": record_id,
                "reference_role": "REGULATOR_WARNING_EVIDENCE",
                "reference_semantics": (
                    "Warning evidence only; not a criminal conviction, scam truth label, or proof that "
                    "an unmatched entity is legitimate."
                ),
                "entity_name_keys": entity_keys,
                "observed_hosts": hosts,
                "regulator": {
                    "name": (row.get("nca_name") or "").strip() or None,
                    "jurisdiction": (row.get("nca_jurisdiction") or "").strip() or None,
                },
                "warning_categories": {
                    "category": (row.get("categories") or "").strip() or None,
                    "detail": (row.get("categories_detailed") or "").strip() or None,
                },
                "evidence_dates": {
                    "validation_date": (row.get("validation_date") or "").strip() or None,
                    "modification_date": (row.get("modification_date") or "").strip() or None,
                },
                "notice_reference_url": (row.get("nca_url") or "").strip() or None,
                "quality_flags": quality_flags,
            }
            records.append(record)
            for key in entity_keys:
                entity_index.setdefault(key, set()).add(record_id)
            for host in hosts:
                host_index.setdefault(host, set()).add(record_id)

    _write_jsonl(output_path, records)
    return {
        "source_id": "iosco_i_scan",
        "record_count": len(records),
        "records_with_entity_name_key": len(records) - quality_counts["records_without_entity_name_key"],
        "records_with_observed_host": len(records) - quality_counts["records_without_observed_host"],
        "quality_counts": dict(sorted(quality_counts.items())),
        "entity_key_collisions": _collision_summary(entity_index),
        "host_collisions": _collision_summary(host_index),
        "output_path": str(output_path),
        "output_sha256": sha256_file(output_path),
    }


def build_sec_index(
    raw_path: Path,
    output_path: Path,
    *,
    source_version: str,
    raw_sha256: str,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    entity_index: dict[str, set[str]] = {}
    host_index: dict[str, set[str]] = {}
    quality_counts: Counter[str] = Counter()

    with gzip.open(raw_path, "rb") as handle:
        for row_number, (_, firm) in enumerate(
            (item for item in ET.iterparse(handle, events=("end",)) if local_name(item[1].tag) == "Firm"),
            start=1,
        ):
            descendants = {local_name(element.tag): element for element in firm.iter()}
            info = descendants.get("Info")
            registration = descendants.get("Rgstn")
            filing = descendants.get("Filing")
            info_attributes = info.attrib if info is not None else {}
            crd_number = (info_attributes.get("FirmCrdNb") or "").strip()
            record_id = crd_number or f"ROW_{row_number:08d}"
            raw_names = [info_attributes.get("BusNm"), info_attributes.get("LegalNm")]
            entity_keys = sorted({key for value in raw_names if (key := normalize_entity_name(value))})
            web_values = [
                (element.text or "").strip()
                for element in firm.iter()
                if local_name(element.tag) == "WebAddr" and (element.text or "").strip()
            ]
            hosts = extract_hosts(web_values)
            quality_flags: list[str] = []
            if not crd_number:
                quality_flags.append("MISSING_CRD_NUMBER")
                quality_counts["records_without_crd_number"] += 1
            if not entity_keys:
                quality_flags.append("NO_USABLE_ENTITY_NAME_KEY")
                quality_counts["records_without_entity_name_key"] += 1
            if not hosts:
                quality_flags.append("NO_USABLE_OBSERVED_HOST")
                quality_counts["records_without_observed_host"] += 1

            registration_attributes = registration.attrib if registration is not None else {}
            filing_attributes = filing.attrib if filing is not None else {}
            record = {
                "schema_version": INDEX_SCHEMA_VERSION,
                "source_id": "sec_iapd",
                "source_version": source_version,
                "source_raw_sha256": raw_sha256,
                "source_record_id": record_id,
                "sec_number": (info_attributes.get("SECNb") or "").strip() or None,
                "reference_role": "REGISTERED_OR_EXEMPT_REPORTING_ENTITY_REFERENCE",
                "reference_semantics": (
                    "Registration reference only; not a content-safety or legitimacy label, and not proof "
                    "that a website is operated by the registered firm."
                ),
                "entity_name_keys": entity_keys,
                "observed_hosts": hosts,
                "registration": {
                    "firm_type": (registration_attributes.get("FirmType") or "").strip() or None,
                    "status": (registration_attributes.get("St") or "").strip() or None,
                    "date": (registration_attributes.get("Dt") or "").strip() or None,
                },
                "filing": {
                    "date": (filing_attributes.get("Dt") or "").strip() or None,
                    "form_version": (filing_attributes.get("FormVrsn") or "").strip() or None,
                },
                "quality_flags": quality_flags,
            }
            records.append(record)
            for key in entity_keys:
                entity_index.setdefault(key, set()).add(record_id)
            for host in hosts:
                host_index.setdefault(host, set()).add(record_id)
            firm.clear()

    _write_jsonl(output_path, records)
    return {
        "source_id": "sec_iapd",
        "record_count": len(records),
        "records_with_entity_name_key": len(records) - quality_counts["records_without_entity_name_key"],
        "records_with_observed_host": len(records) - quality_counts["records_without_observed_host"],
        "quality_counts": dict(sorted(quality_counts.items())),
        "entity_key_collisions": _collision_summary(entity_index),
        "host_collisions": _collision_summary(host_index),
        "output_path": str(output_path),
        "output_sha256": sha256_file(output_path),
    }
