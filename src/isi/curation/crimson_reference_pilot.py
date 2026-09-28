"""Select a deterministic, no-label pilot from Crimson reference matches."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict


PILOT_VERSION = "CRIMSON_EXTERNAL_REFERENCE_REVIEW_PILOT_V1"
SELECTION_SEED = "20260923"


def _digest_rank(host: str) -> str:
    return hashlib.sha256(f"{SELECTION_SEED}|{host}".encode("utf-8")).hexdigest()


def select_pilot(
    queue_records: list[dict[str, object]],
    match_records: list[dict[str, object]],
    *,
    pilot_size: int = 40,
    ambiguous_exact_quota: int = 12,
    hierarchy_quota: int = 10,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    if pilot_size <= 0:
        raise ValueError("pilot_size must be positive")
    queue_by_host: dict[str, dict[str, object]] = {}
    for record in queue_records:
        host = str(record.get("crimson_match_host") or "")
        if not host or host in queue_by_host:
            raise ValueError("queue must contain unique nonempty crimson_match_host values")
        if record.get("label_created") is not False or record.get("identity_resolved") is not False:
            raise ValueError(f"queue record is already decisional: {host}")
        queue_by_host[host] = record

    matches_by_host: dict[str, list[dict[str, object]]] = defaultdict(list)
    for match in match_records:
        host = str(match.get("crimson_match_host") or "")
        if host not in queue_by_host:
            raise ValueError(f"match has no queue record: {host}")
        if match.get("label_created") is not False or match.get("identity_resolved") is not False:
            raise ValueError(f"match record is already decisional: {host}")
        matches_by_host[host].append(match)

    selected: list[tuple[str, str]] = []
    selected_hosts: set[str] = set()

    def add(host: str, bucket: str) -> None:
        if host not in selected_hosts and len(selected) < pilot_size:
            selected.append((host, bucket))
            selected_hosts.add(host)

    sec_hosts = sorted(
        (
            host for host, record in queue_by_host.items()
            if str(record.get("queue_reason", "")).startswith("SEC_")
        ),
        key=lambda host: (
            0 if queue_by_host[host].get("queue_reason") == "SEC_EXACT_HOST" else 1,
            int(queue_by_host[host].get("queue_rank", 0)),
            host,
        ),
    )
    if len(sec_hosts) > pilot_size:
        raise ValueError("pilot_size is smaller than the required all-SEC stratum")
    for host in sec_hosts:
        add(host, "ALL_SEC_MATCHES")

    ambiguous_exact = sorted(
        (
            host for host, record in queue_by_host.items()
            if record.get("queue_reason") == "IOSCO_EXACT_HOST"
            and record.get("shared_reference_host_present") is True
        ),
        key=lambda host: (
            -int(queue_by_host[host].get("match_count", 0)),
            int(queue_by_host[host].get("queue_rank", 0)),
            host,
        ),
    )
    for host in ambiguous_exact[:ambiguous_exact_quota]:
        add(host, "IOSCO_SHARED_EXACT")

    hierarchy_hosts = sorted(
        (
            host for host, record in queue_by_host.items()
            if record.get("queue_reason") == "IOSCO_HOST_HIERARCHY"
        ),
        key=lambda host: (
            0 if queue_by_host[host].get("shared_reference_host_present") else 1,
            int(queue_by_host[host].get("queue_rank", 0)),
            host,
        ),
    )
    for host in hierarchy_hosts[:hierarchy_quota]:
        add(host, "IOSCO_HOST_HIERARCHY")

    fill_hosts = sorted(
        (
            host for host, record in queue_by_host.items()
            if record.get("queue_reason") == "IOSCO_EXACT_HOST" and host not in selected_hosts
        ),
        key=lambda host: (_digest_rank(host), host),
    )
    for host in fill_hosts:
        add(host, "IOSCO_EXACT_HASH_SAMPLE")
        if len(selected) == pilot_size:
            break
    if len(selected) != pilot_size:
        raise ValueError(f"could select only {len(selected)} of {pilot_size} pilot hosts")

    pilot_records: list[dict[str, object]] = []
    evidence_records: list[dict[str, object]] = []
    bucket_counts: Counter[str] = Counter()
    for pilot_rank, (host, bucket) in enumerate(selected, start=1):
        queue = queue_by_host[host]
        matches = matches_by_host[host]
        bucket_counts[bucket] += 1
        distinct_evidence: dict[tuple[str, str], dict[str, object]] = {}
        for match in matches:
            key = (str(match["match_source_id"]), str(match["reference_record_id"]))
            evidence = distinct_evidence.setdefault(key, {
                "pilot_id": f"PILOT_CRIMSON_REF_{pilot_rank:03d}",
                "pilot_rank": pilot_rank,
                "crimson_match_host": host,
                "match_source_id": match["match_source_id"],
                "reference_record_id": match["reference_record_id"],
                "reference_role": match.get("reference_role"),
                "host_relation": match.get("host_relation"),
                "matched_reference_host": match.get("matched_reference_host"),
                "reference_host_record_count": match.get("reference_host_record_count"),
                "notice_reference_url": match.get("notice_reference_url"),
                "sec_number": match.get("sec_number"),
                "crimson_artifact_ids": [],
                "observed_crimson_domains": [],
                "review_status": "UNREVIEWED",
                "identity_resolved": False,
                "label_created": False,
            })
            evidence["crimson_artifact_ids"].append(str(match["crimson_artifact_id"]))
            evidence["observed_crimson_domains"].append(str(match["crimson_domain"]))
        for evidence in distinct_evidence.values():
            evidence["crimson_artifact_ids"] = sorted(set(evidence["crimson_artifact_ids"]))
            evidence["observed_crimson_domains"] = sorted(set(evidence["observed_crimson_domains"]))
            evidence_records.append(evidence)

        source_ids = sorted({str(match["match_source_id"]) for match in matches})
        host_relations = sorted({str(match["host_relation"]) for match in matches})
        notice_urls = sorted({
            str(match["notice_reference_url"])
            for match in matches if match.get("notice_reference_url")
        })
        sec_numbers = sorted({
            str(match["sec_number"]) for match in matches if match.get("sec_number")
        })
        pilot_records.append({
            "pilot_version": PILOT_VERSION,
            "pilot_id": f"PILOT_CRIMSON_REF_{pilot_rank:03d}",
            "pilot_rank": pilot_rank,
            "selection_bucket": bucket,
            "source_queue_rank": queue.get("queue_rank"),
            "crimson_match_host": host,
            "observed_crimson_domains": queue.get("observed_crimson_domains", []),
            "crimson_artifact_ids": queue.get("crimson_artifact_ids", []),
            "reference_sources": source_ids,
            "host_relations": host_relations,
            "reference_match_count": len(distinct_evidence),
            "reference_record_ids": queue.get("reference_record_ids"),
            "iosco_notice_urls": notice_urls,
            "sec_numbers": sec_numbers,
            "shared_reference_host_present": queue.get("shared_reference_host_present"),
            "automatic_interpretation": queue.get("interpretation"),
            "review_status": "NOT_STARTED",
            "identity_relationship": "",
            "evidence_assessment": "",
            "official_reference_checked": "NO",
            "reviewer": "",
            "reviewed_date": None,
            "review_notes": "",
            "second_review_status": "NOT_REQUESTED",
            "second_reviewer": "",
            "adjudication_status": "NOT_READY",
            "training_eligible": "NO",
            "label_created": False,
        })

    evidence_records.sort(
        key=lambda record: (
            int(record["pilot_rank"]),
            str(record["match_source_id"]),
            str(record["reference_record_id"]),
        )
    )
    return pilot_records, evidence_records, {
        "pilot_version": PILOT_VERSION,
        "selection_seed": SELECTION_SEED,
        "pilot_record_count": len(pilot_records),
        "evidence_record_count": len(evidence_records),
        "selection_bucket_counts": dict(sorted(bucket_counts.items())),
        "source_host_counts": {
            "sec_iapd": sum("sec_iapd" in record["reference_sources"] for record in pilot_records),
            "iosco_i_scan": sum("iosco_i_scan" in record["reference_sources"] for record in pilot_records),
        },
        "safety_contract": {
            "network_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
            "manual_review_required": True,
        },
    }
