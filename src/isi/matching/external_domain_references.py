"""Match Crimson hosts to frozen public-reference indices without network access."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.isi.normalization.external_references import canonicalize_host, sha256_file


MATCH_VERSION = "CRIMSON_EXTERNAL_REFERENCE_MATCH_V1"
RELATION_PRIORITY = {
    "EXACT_HOST": 0,
    "CRIMSON_SUBDOMAIN_OF_REFERENCE_HOST": 1,
    "REFERENCE_SUBDOMAIN_OF_CRIMSON_HOST": 2,
}
QUEUE_PRIORITY = {
    "IOSCO_AND_SEC_REFERENCE": 0,
    "IOSCO_EXACT_HOST": 1,
    "IOSCO_HOST_HIERARCHY": 2,
    "SEC_EXACT_HOST": 3,
    "SEC_HOST_HIERARCHY": 4,
}


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: record must be an object")
            records.append(record)
    return records


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _proper_host_suffixes(host: str) -> list[str]:
    labels = host.split(".")
    return [".".join(labels[index:]) for index in range(1, len(labels) - 1)]


def build_reference_maps(
    reference_records: list[dict[str, object]], expected_source_id: str
) -> tuple[dict[str, list[dict[str, object]]], dict[str, set[str]]]:
    by_host: dict[str, list[dict[str, object]]] = defaultdict(list)
    descendants_by_ancestor: dict[str, set[str]] = defaultdict(set)
    record_ids: set[str] = set()
    for line_number, record in enumerate(reference_records, start=1):
        if record.get("source_id") != expected_source_id:
            raise ValueError(f"reference line {line_number}: unexpected source_id")
        record_id = str(record.get("source_record_id") or "")
        if not record_id or record_id in record_ids:
            raise ValueError(f"reference line {line_number}: missing or duplicate source_record_id")
        record_ids.add(record_id)
        descriptor = {
            "source_record_id": record_id,
            "reference_role": record.get("reference_role"),
            "reference_semantics": record.get("reference_semantics"),
            "notice_reference_url": record.get("notice_reference_url"),
            "sec_number": record.get("sec_number"),
        }
        observed_hosts = record.get("observed_hosts", [])
        if not isinstance(observed_hosts, list):
            raise ValueError(f"reference line {line_number}: observed_hosts must be a list")
        for raw_host in observed_hosts:
            host = canonicalize_host(str(raw_host))
            if not host:
                raise ValueError(f"reference line {line_number}: invalid normalized host")
            by_host[host].append(descriptor)
            for ancestor in _proper_host_suffixes(host):
                descendants_by_ancestor[ancestor].add(host)
    for host in by_host:
        by_host[host].sort(key=lambda item: str(item["source_record_id"]))
    return dict(by_host), dict(descendants_by_ancestor)


def match_host(
    crimson_host: str,
    source_id: str,
    by_host: dict[str, list[dict[str, object]]],
    descendants_by_ancestor: dict[str, set[str]],
) -> list[dict[str, object]]:
    """Return one best host relation per source record; never resolve identity."""

    candidate = canonicalize_host(crimson_host)
    if not candidate:
        raise ValueError(f"Invalid Crimson host: {crimson_host!r}")
    possible: list[tuple[str, str, dict[str, object]]] = []
    for descriptor in by_host.get(candidate, []):
        possible.append(("EXACT_HOST", candidate, descriptor))
    for reference_host in _proper_host_suffixes(candidate):
        for descriptor in by_host.get(reference_host, []):
            possible.append(("CRIMSON_SUBDOMAIN_OF_REFERENCE_HOST", reference_host, descriptor))
    for reference_host in sorted(descendants_by_ancestor.get(candidate, set())):
        for descriptor in by_host[reference_host]:
            possible.append(("REFERENCE_SUBDOMAIN_OF_CRIMSON_HOST", reference_host, descriptor))

    best_by_record: dict[str, tuple[str, str, dict[str, object]]] = {}
    for relation, reference_host, descriptor in possible:
        record_id = str(descriptor["source_record_id"])
        rank = (RELATION_PRIORITY[relation], -len(reference_host.split(".")), reference_host)
        current = best_by_record.get(record_id)
        if current is None:
            best_by_record[record_id] = (relation, reference_host, descriptor)
            continue
        current_rank = (
            RELATION_PRIORITY[current[0]], -len(current[1].split(".")), current[1]
        )
        if rank < current_rank:
            best_by_record[record_id] = (relation, reference_host, descriptor)

    matches: list[dict[str, object]] = []
    for record_id, (relation, reference_host, descriptor) in sorted(best_by_record.items()):
        matches.append({
            "match_source_id": source_id,
            "reference_record_id": record_id,
            "reference_role": descriptor.get("reference_role"),
            "reference_semantics": descriptor.get("reference_semantics"),
            "matched_reference_host": reference_host,
            "host_relation": relation,
            "reference_host_record_count": len(by_host[reference_host]),
            "notice_reference_url": descriptor.get("notice_reference_url"),
            "sec_number": descriptor.get("sec_number"),
        })
    return matches


def queue_reason(matches: list[dict[str, object]]) -> str:
    source_ids = {str(match["match_source_id"]) for match in matches}
    if source_ids == {"iosco_i_scan", "sec_iapd"}:
        return "IOSCO_AND_SEC_REFERENCE"
    has_exact = any(match["host_relation"] == "EXACT_HOST" for match in matches)
    if source_ids == {"iosco_i_scan"}:
        return "IOSCO_EXACT_HOST" if has_exact else "IOSCO_HOST_HIERARCHY"
    if source_ids == {"sec_iapd"}:
        return "SEC_EXACT_HOST" if has_exact else "SEC_HOST_HIERARCHY"
    raise ValueError(f"Unexpected match sources: {sorted(source_ids)}")


def queue_interpretation(reason: str) -> str:
    if reason == "IOSCO_AND_SEC_REFERENCE":
        return (
            "Both warning and registration references exist. This may reflect impersonation, shared "
            "infrastructure, or distinct entities; manual evidence review is required."
        )
    if reason.startswith("IOSCO_"):
        return (
            "Regulator-warning host evidence for review only; not a conviction or automatic scam label."
        )
    return (
        "Registration-host reference for review only; not proof of legitimacy or proof that the site "
        "is operated by the registered firm."
    )


def build_match_outputs(
    crimson_path: Path,
    iosco_path: Path,
    sec_path: Path,
    matches_output: Path,
    queue_output: Path,
    *,
    input_hashes: dict[str, str],
) -> dict[str, object]:
    crimson_records = load_jsonl(crimson_path)
    iosco_records = load_jsonl(iosco_path)
    sec_records = load_jsonl(sec_path)
    iosco_by_host, iosco_descendants = build_reference_maps(iosco_records, "iosco_i_scan")
    sec_by_host, sec_descendants = build_reference_maps(sec_records, "sec_iapd")

    matches_output_records: list[dict[str, object]] = []
    queue_by_host: dict[str, dict[str, object]] = {}
    artifact_ids: set[str] = set()
    raw_crimson_domains: set[str] = set()
    crimson_match_hosts: set[str] = set()
    matches_by_host: dict[str, list[dict[str, object]]] = {}
    relation_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    ambiguous_match_pair_count = 0

    for line_number, artifact in enumerate(crimson_records, start=1):
        if artifact.get("source_id") != "crimson_www_2025":
            raise ValueError(f"Crimson line {line_number}: unexpected source_id")
        artifact_id = str(artifact.get("artifact_id") or "")
        raw_domain = str(artifact.get("domain") or "").strip().lower().rstrip(".")
        canonical_host = canonicalize_host(raw_domain)
        if not artifact_id or artifact_id in artifact_ids:
            raise ValueError(f"Crimson line {line_number}: missing or duplicate artifact_id")
        if not canonical_host or raw_domain in raw_crimson_domains:
            raise ValueError(f"Crimson line {line_number}: invalid or duplicate source domain")
        artifact_ids.add(artifact_id)
        raw_crimson_domains.add(raw_domain)
        crimson_match_hosts.add(canonical_host)

        if canonical_host not in matches_by_host:
            host_matches = match_host(
                canonical_host, "iosco_i_scan", iosco_by_host, iosco_descendants
            )
            host_matches.extend(
                match_host(canonical_host, "sec_iapd", sec_by_host, sec_descendants)
            )
            host_matches.sort(
                key=lambda item: (
                    RELATION_PRIORITY[str(item["host_relation"])],
                    str(item["match_source_id"]),
                    str(item["reference_record_id"]),
                )
            )
            matches_by_host[canonical_host] = host_matches
        artifact_matches = matches_by_host[canonical_host]
        if not artifact_matches:
            continue
        for match in artifact_matches:
            match_key = (
                f"{artifact_id}|{match['match_source_id']}|{match['reference_record_id']}|"
                f"{match['host_relation']}|{match['matched_reference_host']}"
            )
            output_record = {
                "match_id": "MATCH_" + hashlib.sha256(match_key.encode("utf-8")).hexdigest()[:24].upper(),
                "match_version": MATCH_VERSION,
                "crimson_artifact_id": artifact_id,
                "crimson_domain": raw_domain,
                "crimson_match_host": canonical_host,
                **match,
                "review_status": "UNREVIEWED",
                "identity_resolved": False,
                "label_created": False,
            }
            matches_output_records.append(output_record)
            relation_counts[str(match["host_relation"])] += 1
            source_counts[str(match["match_source_id"])] += 1
            ambiguous_match_pair_count += int(int(match["reference_host_record_count"]) > 1)

        if canonical_host not in queue_by_host:
            reason = queue_reason(artifact_matches)
            reason_counts[reason] += 1
            ids_by_source = {
                source_id: sorted({
                    str(match["reference_record_id"])
                    for match in artifact_matches
                    if match["match_source_id"] == source_id
                })
                for source_id in ("iosco_i_scan", "sec_iapd")
            }
            queue_by_host[canonical_host] = {
                "match_version": MATCH_VERSION,
                "crimson_match_host": canonical_host,
                "crimson_artifact_ids": [],
                "observed_crimson_domains": [],
                "queue_reason": reason,
                "queue_priority": QUEUE_PRIORITY[reason],
                "match_count": len(artifact_matches),
                "exact_match_count": sum(
                    match["host_relation"] == "EXACT_HOST" for match in artifact_matches
                ),
                "hierarchy_match_count": sum(
                    match["host_relation"] != "EXACT_HOST" for match in artifact_matches
                ),
                "reference_record_ids": ids_by_source,
                "shared_reference_host_present": any(
                    int(match["reference_host_record_count"]) > 1 for match in artifact_matches
                ),
                "review_status": "UNREVIEWED",
                "identity_resolved": False,
                "label_created": False,
                "interpretation": queue_interpretation(reason),
            }
        queue_by_host[canonical_host]["crimson_artifact_ids"].append(artifact_id)
        queue_by_host[canonical_host]["observed_crimson_domains"].append(raw_domain)

    queue_records = list(queue_by_host.values())
    for record in queue_records:
        record["crimson_artifact_ids"].sort()
        record["observed_crimson_domains"].sort()
    queue_records.sort(
        key=lambda item: (
            int(item["queue_priority"]),
            -int(item["exact_match_count"]),
            -int(item["match_count"]),
            str(item["crimson_match_host"]),
        )
    )
    for rank, record in enumerate(queue_records, start=1):
        record["queue_rank"] = rank
    matches_output_records.sort(
        key=lambda item: (
            str(item["crimson_match_host"]),
            str(item["crimson_domain"]),
            str(item["match_source_id"]),
            str(item["reference_record_id"]),
        )
    )
    write_jsonl(matches_output, matches_output_records)
    write_jsonl(queue_output, queue_records)

    return {
        "match_version": MATCH_VERSION,
        "status": "FROZEN_OFFLINE_REFERENCE_MATCHES_NOT_LABELS",
        "inputs": {
            "crimson_path": str(crimson_path),
            "crimson_sha256": input_hashes["crimson"],
            "iosco_path": str(iosco_path),
            "iosco_sha256": input_hashes["iosco"],
            "sec_path": str(sec_path),
            "sec_sha256": input_hashes["sec"],
        },
        "coverage": {
            "crimson_record_count": len(crimson_records),
            "unique_crimson_match_host_count": len(crimson_match_hosts),
            "crimson_records_with_reference_match": sum(
                len(record["crimson_artifact_ids"]) for record in queue_records
            ),
            "crimson_records_without_reference_match": len(crimson_records) - sum(
                len(record["crimson_artifact_ids"]) for record in queue_records
            ),
            "unique_crimson_match_hosts_with_reference_match": len(queue_records),
            "unique_crimson_match_hosts_without_reference_match": len(crimson_match_hosts) - len(queue_records),
            "reference_match_pair_count": len(matches_output_records),
            "ambiguous_match_pair_count": ambiguous_match_pair_count,
            "pair_counts_by_source": dict(sorted(source_counts.items())),
            "pair_counts_by_host_relation": dict(sorted(relation_counts.items())),
            "queue_counts_by_reason": dict(sorted(reason_counts.items())),
        },
        "outputs": {
            "reference_matches": {
                "path": str(matches_output),
                "sha256": sha256_file(matches_output),
                "record_count": len(matches_output_records),
            },
            "review_queue": {
                "path": str(queue_output),
                "sha256": sha256_file(queue_output),
                "record_count": len(queue_records),
            },
        },
        "matching_policy": {
            "relations": list(RELATION_PRIORITY),
            "public_suffix_inference": False,
            "identity_resolution_performed": False,
            "unmatched_means_safe": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "labels_created": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
            "automatic_entity_resolution_allowed": False,
            "manual_evidence_review_required": True,
        },
    }
