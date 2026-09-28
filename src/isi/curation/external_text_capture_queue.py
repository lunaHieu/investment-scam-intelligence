"""Deterministically select external-text capture candidates from reference indices.

The output is a collection queue, not a labeled dataset.  IOSCO alerts are
warning evidence and SEC/IAPD records are registration references; neither is
promoted to ground truth by this module.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlparse


BLOCKED_SHARED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "linktr.ee",
    "medium.com",
    "substack.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}

LEGAL_OR_GENERIC_ENTITY_TOKENS = {
    "adviser",
    "advisers",
    "advisor",
    "advisors",
    "asset",
    "capital",
    "company",
    "corp",
    "corporation",
    "financial",
    "fund",
    "group",
    "inc",
    "investment",
    "investments",
    "llc",
    "llp",
    "lp",
    "ltd",
    "management",
    "partners",
    "services",
    "wealth",
}


def _stable_key(seed: str, target: str, host: str, source_record_id: str) -> str:
    value = f"{seed}|{target}|{host}|{source_record_id}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _clean_single_host(record: dict[str, object]) -> str | None:
    hosts = record.get("observed_hosts")
    if not isinstance(hosts, list) or len(hosts) != 1:
        return None
    host = hosts[0]
    if not isinstance(host, str):
        return None
    host = host.strip().lower().rstrip(".")
    if not host or host in BLOCKED_SHARED_HOSTS or "." not in host:
        return None
    return host


def _valid_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _entity_keys(record: dict[str, object]) -> list[str]:
    values = record.get("entity_name_keys")
    if not isinstance(values, list):
        return []
    return sorted({value for value in values if isinstance(value, str) and value.strip()})


def _base_queue_record(
    *,
    candidate_id: str,
    target: str,
    rank: int,
    host: str,
    record: dict[str, object],
    official_reference: dict[str, object],
    acquisition_guardrail: str,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "target_outcome": target,
        "selection_rank_within_target": rank,
        "candidate_host": host,
        "source_id": record.get("source_id"),
        "source_record_id": str(record.get("source_record_id")),
        "entity_name_keys": _entity_keys(record),
        "reference_role": record.get("reference_role"),
        "official_reference": official_reference,
        "artifact_requirement": {
            "allowed_artifact_types": ["POST", "MESSAGE", "WEBSITE_SNAPSHOT"],
            "observed_text_required": True,
            "source_capture_and_sha256_required": True,
            "warning_or_registry_text_as_model_input_allowed": False,
        },
        "review_state": {
            "artifact_capture": "MISSING",
            "identity_resolution": "UNRESOLVED",
            "ground_truth_status": "UNCERTAIN",
            "label_confidence": "LOW",
            "review_status": "UNREVIEWED",
        },
        "acquisition_guardrail": acquisition_guardrail,
        "training_eligible": "NO",
        "label_created": False,
    }


def select_capture_candidates(
    iosco_records: list[dict[str, object]],
    sec_records: list[dict[str, object]],
    *,
    per_target: int = 15,
    seed: str = "20260923",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Select balanced capture candidates while preserving an unresolved state."""

    if per_target < 1:
        raise ValueError("per_target must be positive")

    iosco_all_hosts = {
        host.strip().lower().rstrip(".")
        for record in iosco_records
        for host in (record.get("observed_hosts") or [])
        if isinstance(host, str)
    }
    sec_host_counts = Counter(
        host
        for record in sec_records
        for host in (record.get("observed_hosts") or [])
        if isinstance(host, str)
    )

    exclusion_counts: Counter[str] = Counter()
    iosco_pool: list[tuple[dict[str, object], str]] = []
    seen_iosco_hosts: set[str] = set()
    for record in iosco_records:
        host = _clean_single_host(record)
        if host is None:
            exclusion_counts["iosco_not_single_clean_host"] += 1
            continue
        if record.get("quality_flags") not in ([], None):
            exclusion_counts["iosco_quality_flag"] += 1
            continue
        notice_url = record.get("notice_reference_url")
        if not _valid_https_url(notice_url):
            exclusion_counts["iosco_missing_https_notice"] += 1
            continue
        if urlparse(str(notice_url)).hostname in {host, f"www.{host}"}:
            exclusion_counts["iosco_notice_is_candidate_host"] += 1
            continue
        regulator = record.get("regulator")
        if not isinstance(regulator, dict) or not regulator.get("name") or not regulator.get("jurisdiction"):
            exclusion_counts["iosco_missing_regulator"] += 1
            continue
        if not _entity_keys(record):
            exclusion_counts["iosco_missing_entity"] += 1
            continue
        if host in seen_iosco_hosts:
            exclusion_counts["iosco_duplicate_host"] += 1
            continue
        seen_iosco_hosts.add(host)
        iosco_pool.append((record, host))

    sec_pool: list[tuple[dict[str, object], str]] = []
    for record in sec_records:
        host = _clean_single_host(record)
        if host is None:
            exclusion_counts["sec_not_single_clean_host"] += 1
            continue
        if record.get("quality_flags") not in ([], None):
            exclusion_counts["sec_quality_flag"] += 1
            continue
        registration = record.get("registration")
        if not isinstance(registration, dict):
            exclusion_counts["sec_missing_registration"] += 1
            continue
        if registration.get("firm_type") != "Registered" or registration.get("status") != "APPROVED":
            exclusion_counts["sec_not_registered_approved"] += 1
            continue
        if sec_host_counts[host] != 1:
            exclusion_counts["sec_shared_host"] += 1
            continue
        if host in iosco_all_hosts:
            exclusion_counts["sec_iosco_host_collision"] += 1
            continue
        if not record.get("sec_number") or not _entity_keys(record):
            exclusion_counts["sec_missing_identity_field"] += 1
            continue
        sec_pool.append((record, host))

    def warning_sort(item: tuple[dict[str, object], str]) -> tuple[str, str]:
        record, host = item
        dates = record.get("evidence_dates") if isinstance(record.get("evidence_dates"), dict) else {}
        validation_date = str(dates.get("validation_date") or "")
        return (
            f"{99999999 - int(validation_date.replace('-', '')):08d}"
            if validation_date.replace("-", "").isdigit()
            else "99999999",
            _stable_key(seed, "CONFIRMED_CANDIDATE", host, str(record.get("source_record_id"))),
        )

    iosco_pool.sort(key=warning_sort)
    max_per_jurisdiction = max(1, math.ceil(per_target / 5))
    selected_iosco: list[tuple[dict[str, object], str]] = []
    jurisdiction_counts: Counter[str] = Counter()
    for record, host in iosco_pool:
        regulator = record["regulator"]
        jurisdiction = str(regulator["jurisdiction"])
        if jurisdiction_counts[jurisdiction] >= max_per_jurisdiction:
            continue
        selected_iosco.append((record, host))
        jurisdiction_counts[jurisdiction] += 1
        if len(selected_iosco) == per_target:
            break
    if len(selected_iosco) < per_target:
        selected_hosts = {host for _, host in selected_iosco}
        for record, host in iosco_pool:
            if host in selected_hosts:
                continue
            selected_iosco.append((record, host))
            selected_hosts.add(host)
            if len(selected_iosco) == per_target:
                break

    sec_pool.sort(
        key=lambda item: _stable_key(
            seed,
            "LEGITIMATE_CANDIDATE",
            item[1],
            str(item[0].get("source_record_id")),
        )
    )
    selected_sec = sec_pool[:per_target]

    if len(selected_iosco) < per_target or len(selected_sec) < per_target:
        raise ValueError(
            "Insufficient clean candidates after safety filters: "
            f"IOSCO={len(selected_iosco)}, SEC={len(selected_sec)}, required={per_target}"
        )

    queue: list[dict[str, object]] = []
    for rank, (record, host) in enumerate(selected_iosco, start=1):
        queue.append(
            _base_queue_record(
                candidate_id=f"EXTCAP_CONF_{rank:03d}",
                target="CONFIRMED_CANDIDATE",
                rank=rank,
                host=host,
                record=record,
                official_reference={
                    "url": record.get("notice_reference_url"),
                    "regulator": record.get("regulator"),
                    "evidence_dates": record.get("evidence_dates"),
                    "warning_categories": record.get("warning_categories"),
                },
                acquisition_guardrail=(
                    "Review the official regulator notice first. Obtain historical or regulator-preserved "
                    "solicitation content; do not open the live candidate host by default. The warning alone "
                    "is evidence, never the model-input text or an automatic label."
                ),
            )
        )
    for rank, (record, host) in enumerate(selected_sec, start=1):
        crd = str(record.get("source_record_id"))
        queue.append(
            _base_queue_record(
                candidate_id=f"EXTCAP_LEGIT_{rank:03d}",
                target="LEGITIMATE_CANDIDATE",
                rank=rank,
                host=host,
                record=record,
                official_reference={
                    "url": f"https://adviserinfo.sec.gov/firm/summary/{crd}",
                    "sec_number": record.get("sec_number"),
                    "registration": record.get("registration"),
                    "filing": record.get("filing"),
                },
                acquisition_guardrail=(
                    "Confirm the SEC/IAPD identity and exact registered host before a controlled browser "
                    "capture. Registration supports identity only; it does not prove every page, message, "
                    "representative, or offer is legitimate."
                ),
            )
        )

    report = {
        "selection_seed": seed,
        "requested_per_target": per_target,
        "input_counts": {"iosco": len(iosco_records), "sec_iapd": len(sec_records)},
        "eligible_pool_counts": {"iosco": len(iosco_pool), "sec_iapd": len(sec_pool)},
        "selected_counts": {
            "CONFIRMED_CANDIDATE": len(selected_iosco),
            "LEGITIMATE_CANDIDATE": len(selected_sec),
            "total": len(queue),
        },
        "selected_warning_jurisdictions": dict(sorted(jurisdiction_counts.items())),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "readiness": {
            "capture_complete": 0,
            "reconciled": 0,
            "eligible_for_external_evaluation": 0,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
        },
    }
    return queue, report


def _domain_identity_affinity(record: dict[str, object], host: str) -> float:
    label = re.sub(r"[^a-z0-9]+", "", host.split(".", 1)[0].casefold())
    scores = []
    for entity in _entity_keys(record):
        tokens = re.findall(r"[a-z0-9]+", entity.casefold())
        content_tokens = [token for token in tokens if token not in LEGAL_OR_GENERIC_ENTITY_TOKENS]
        comparison_tokens = content_tokens or tokens
        if not label or not comparison_tokens:
            continue
        coverage = sum(token in label for token in comparison_tokens) / len(comparison_tokens)
        compact = "".join(tokens)
        similarity = SequenceMatcher(None, label, compact).ratio()
        scores.append(0.7 * coverage + 0.3 * similarity)
    return max(scores, default=0.0)


def select_legitimate_reserve_candidates(
    iosco_records: list[dict[str, object]],
    sec_records: list[dict[str, object]],
    existing_hosts: set[str],
    *,
    reserve_size: int = 30,
    seed: str = "20260924",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Select a higher-affinity SEC reserve queue without creating labels."""

    if reserve_size < 1:
        raise ValueError("reserve_size must be positive")
    normalized_existing = {host.casefold().rstrip(".") for host in existing_hosts}
    iosco_hosts = {
        host.casefold().rstrip(".")
        for record in iosco_records
        for host in (record.get("observed_hosts") or [])
        if isinstance(host, str)
    }
    sec_host_counts = Counter(
        host.casefold().rstrip(".")
        for record in sec_records
        for host in (record.get("observed_hosts") or [])
        if isinstance(host, str)
    )
    exclusions: Counter[str] = Counter()
    pool: list[tuple[dict[str, object], str, float]] = []
    for record in sec_records:
        host = _clean_single_host(record)
        if host is None:
            exclusions["not_single_clean_host"] += 1
            continue
        if host in normalized_existing:
            exclusions["already_in_primary_queue"] += 1
            continue
        if host in iosco_hosts:
            exclusions["iosco_host_collision"] += 1
            continue
        if sec_host_counts[host] != 1:
            exclusions["shared_sec_host"] += 1
            continue
        if record.get("quality_flags") not in ([], None):
            exclusions["quality_flag"] += 1
            continue
        registration = record.get("registration")
        filing = record.get("filing")
        if not isinstance(registration, dict) or not isinstance(filing, dict):
            exclusions["missing_registration_or_filing"] += 1
            continue
        if registration.get("firm_type") != "Registered" or registration.get("status") != "APPROVED":
            exclusions["not_registered_approved"] += 1
            continue
        registration_date = str(registration.get("date") or "")
        filing_date = str(filing.get("date") or "")
        if not registration_date or registration_date > "2023-12-31":
            exclusions["insufficient_registration_tenure"] += 1
            continue
        if not filing_date or filing_date < "2025-01-01":
            exclusions["filing_not_recent"] += 1
            continue
        affinity = _domain_identity_affinity(record, host)
        if affinity < 0.45:
            exclusions["low_domain_identity_affinity"] += 1
            continue
        pool.append((record, host, affinity))

    pool.sort(
        key=lambda item: (
            -item[2],
            str(item[0]["registration"].get("date") or ""),
            _stable_key(seed, "LEGITIMATE_RESERVE_CANDIDATE", item[1], str(item[0].get("source_record_id"))),
        )
    )
    selected = pool[:reserve_size]
    if len(selected) < reserve_size:
        raise ValueError(f"Insufficient reserve candidates: {len(selected)} < {reserve_size}")

    queue = []
    for rank, (record, host, affinity) in enumerate(selected, start=1):
        crd = str(record.get("source_record_id"))
        candidate = _base_queue_record(
            candidate_id=f"EXTCAP_RESERVE_LEGIT_{rank:03d}",
            target="LEGITIMATE_RESERVE_CANDIDATE",
            rank=rank,
            host=host,
            record=record,
            official_reference={
                "url": f"https://adviserinfo.sec.gov/firm/summary/{crd}",
                "sec_number": record.get("sec_number"),
                "registration": record.get("registration"),
                "filing": record.get("filing"),
            },
            acquisition_guardrail=(
                "Confirm the SEC/IAPD identity and exact filed host before controlled capture. "
                "This reserve rank improves identity affinity only; it does not create a legitimacy label."
            ),
        )
        candidate["selection_signals"] = {
            "domain_identity_affinity": round(affinity, 6),
            "registration_date": record["registration"].get("date"),
            "filing_date": record["filing"].get("date"),
            "sec_host_unique": True,
            "iosco_collision": False,
        }
        queue.append(candidate)

    report = {
        "selection_seed": seed,
        "requested_reserve_size": reserve_size,
        "input_counts": {"iosco": len(iosco_records), "sec_iapd": len(sec_records)},
        "existing_primary_host_count": len(normalized_existing),
        "eligible_pool_count": len(pool),
        "selected_count": len(queue),
        "affinity_range": {
            "minimum": min(item[2] for item in selected),
            "maximum": max(item[2] for item in selected),
        },
        "exclusion_counts": dict(sorted(exclusions.items())),
        "readiness": {"captured": 0, "reconciled": 0, "eligible": 0},
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
        },
    }
    return queue, report


def select_confirmed_reserve_candidates(
    iosco_records: list[dict[str, object]],
    existing_hosts: set[str],
    *,
    reserve_size: int = 40,
    seed: str = "20260924-confirmed",
    candidate_id_prefix: str = "EXTCAP_RESERVE_CONF",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Select recent, high-affinity IOSCO reserve candidates without labeling them."""

    if reserve_size < 1:
        raise ValueError("reserve_size must be positive")
    normalized_existing = {host.casefold().rstrip(".") for host in existing_hosts}
    iosco_host_counts = Counter(
        host.casefold().rstrip(".")
        for record in iosco_records
        for host in (record.get("observed_hosts") or [])
        if isinstance(host, str)
    )
    exclusions: Counter[str] = Counter()
    pool: list[tuple[dict[str, object], str, float, str]] = []
    for record in iosco_records:
        host = _clean_single_host(record)
        if host is None:
            exclusions["not_single_clean_host"] += 1
            continue
        if host in normalized_existing:
            exclusions["already_in_primary_queue"] += 1
            continue
        if iosco_host_counts[host] != 1:
            exclusions["duplicate_iosco_host"] += 1
            continue
        if record.get("quality_flags") not in ([], None):
            exclusions["quality_flag"] += 1
            continue
        notice_url = record.get("notice_reference_url")
        if not _valid_https_url(notice_url):
            exclusions["missing_https_notice"] += 1
            continue
        if urlparse(str(notice_url)).hostname in {host, f"www.{host}"}:
            exclusions["notice_is_candidate_host"] += 1
            continue
        regulator = record.get("regulator")
        if not isinstance(regulator, dict) or not regulator.get("name") or not regulator.get("jurisdiction"):
            exclusions["missing_regulator"] += 1
            continue
        if not _entity_keys(record):
            exclusions["missing_entity"] += 1
            continue
        dates = record.get("evidence_dates") if isinstance(record.get("evidence_dates"), dict) else {}
        validation_date = str(dates.get("validation_date") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", validation_date) or validation_date < "2025-01-01":
            exclusions["warning_not_recent"] += 1
            continue
        affinity = _domain_identity_affinity(record, host)
        if affinity < 0.45:
            exclusions["low_domain_identity_affinity"] += 1
            continue
        pool.append((record, host, affinity, validation_date))

    pool.sort(
        key=lambda item: (
            -item[2],
            -int(item[3].replace("-", "")),
            _stable_key(
                seed,
                "CONFIRMED_RESERVE_CANDIDATE",
                item[1],
                str(item[0].get("source_record_id")),
            ),
        )
    )
    max_per_jurisdiction = max(2, math.ceil(reserve_size / 4))
    selected: list[tuple[dict[str, object], str, float, str]] = []
    jurisdiction_counts: Counter[str] = Counter()
    for item in pool:
        jurisdiction = str(item[0]["regulator"]["jurisdiction"])
        if jurisdiction_counts[jurisdiction] >= max_per_jurisdiction:
            continue
        selected.append(item)
        jurisdiction_counts[jurisdiction] += 1
        if len(selected) == reserve_size:
            break
    if len(selected) < reserve_size:
        selected_hosts = {item[1] for item in selected}
        for item in pool:
            if item[1] in selected_hosts:
                continue
            selected.append(item)
            selected_hosts.add(item[1])
            if len(selected) == reserve_size:
                break
    if len(selected) < reserve_size:
        raise ValueError(f"Insufficient confirmed reserve candidates: {len(selected)} < {reserve_size}")

    queue = []
    for rank, (record, host, affinity, validation_date) in enumerate(selected, start=1):
        candidate = _base_queue_record(
            candidate_id=f"{candidate_id_prefix}_{rank:03d}",
            target="CONFIRMED_RESERVE_CANDIDATE",
            rank=rank,
            host=host,
            record=record,
            official_reference={
                "url": record.get("notice_reference_url"),
                "regulator": record.get("regulator"),
                "evidence_dates": record.get("evidence_dates"),
                "warning_categories": record.get("warning_categories"),
            },
            acquisition_guardrail=(
                "Use regulator evidence and lawful historical captures only; do not open the live candidate "
                "host by default. A reserve rank is not a label, and warning text is never model input."
            ),
        )
        candidate["selection_signals"] = {
            "domain_identity_affinity": round(affinity, 6),
            "warning_validation_date": validation_date,
            "iosco_host_unique": True,
        }
        queue.append(candidate)

    report = {
        "selection_seed": seed,
        "requested_reserve_size": reserve_size,
        "input_iosco_count": len(iosco_records),
        "existing_primary_host_count": len(normalized_existing),
        "eligible_pool_count": len(pool),
        "selected_count": len(queue),
        "selected_jurisdictions": dict(sorted(jurisdiction_counts.items())),
        "affinity_range": {
            "minimum": min(item[2] for item in selected),
            "maximum": max(item[2] for item in selected),
        },
        "exclusion_counts": dict(sorted(exclusions.items())),
        "readiness": {"captured": 0, "reconciled": 0, "eligible": 0},
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
        },
    }
    return queue, report
