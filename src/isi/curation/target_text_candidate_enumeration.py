"""Deterministic, label-free enumeration for the Target Text Corpus V1 pilot."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlparse


CHANNELS = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": {
        "stratum": "CONFIRMED",
        "sources": {"iosco_i_scan", "fca_warning_list", "ubcknn_warnings"},
        "reference_role": "CANDIDATE_DISCOVERY_AND_CASE_EVIDENCE_ONLY",
        "candidate_prefix": "CONF_REG",
    },
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": {
        "stratum": "CONFIRMED",
        "sources": {"cftc_red_list"},
        "reference_role": "CANDIDATE_DISCOVERY_AND_CASE_EVIDENCE_ONLY",
        "candidate_prefix": "CONF_CFTC",
    },
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": {
        "stratum": "LEGITIMATE",
        "sources": {"sec_iapd"},
        "reference_role": "OFFICIAL_ENTITY_REFERENCE_ONLY",
        "candidate_prefix": "LEGIT_IAPD",
    },
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": {
        "stratum": "LEGITIMATE",
        "sources": {"sec_edgar_company_submissions"},
        "reference_role": "OFFICIAL_ENTITY_REFERENCE_ONLY",
        "candidate_prefix": "LEGIT_EDGAR",
    },
}

REQUIRED_REFERENCE_FIELDS = {
    "source_id",
    "source_record_id",
    "reference_url",
    "reference_observed_at",
    "reference_sha256",
    "entity_name_from_reference",
    "candidate_url",
    "normalized_host",
    "identity_linkage_basis",
    "opened_normalized_host",
    "opened_reference_identity",
    "legacy_component",
}


def _normalized_entity(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def _stable_key(seed: str, channel_id: str, record: dict[str, Any]) -> str:
    payload = "|".join(
        (
            seed,
            channel_id,
            str(record["source_id"]),
            str(record["source_record_id"]),
            str(record["normalized_host"]),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_reference_record(channel_id: str, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_REFERENCE_FIELDS - set(record))
    if missing:
        return [f"missing_fields:{','.join(missing)}"]
    channel = CHANNELS[channel_id]
    if record.get("source_id") not in channel["sources"]:
        errors.append("unregistered_source_for_channel")
    if not str(record.get("source_record_id", "")).strip():
        errors.append("missing_source_record_id")
    reference_url = urlparse(str(record.get("reference_url", "")))
    if reference_url.scheme != "https" or not reference_url.netloc:
        errors.append("invalid_reference_https_url")
    if not re.fullmatch(r"[a-f0-9]{64}", str(record.get("reference_sha256", ""))):
        errors.append("invalid_reference_sha256")
    candidate_url = urlparse(str(record.get("candidate_url", "")))
    normalized_host = str(record.get("normalized_host", "")).casefold().rstrip(".")
    if candidate_url.scheme not in {"http", "https"} or not candidate_url.hostname:
        errors.append("invalid_candidate_url")
    elif candidate_url.hostname.casefold().rstrip(".") != normalized_host:
        errors.append("candidate_url_host_mismatch")
    if not normalized_host or "." not in normalized_host:
        errors.append("invalid_normalized_host")
    if not str(record.get("entity_name_from_reference", "")).strip():
        errors.append("missing_entity_name")
    if not str(record.get("identity_linkage_basis", "")).strip():
        errors.append("missing_identity_linkage_basis")
    if record.get("opened_normalized_host") != "PASS":
        errors.append("opened_normalized_host_not_clear")
    if record.get("opened_reference_identity") != "PASS":
        errors.append("opened_reference_identity_not_clear")
    if record.get("legacy_component") not in {"PASS", "MANUAL_CLEARED"}:
        errors.append("legacy_component_not_clear")
    return errors


def _candidate_record(
    channel_id: str,
    record: dict[str, Any],
    *,
    wave_id: str,
    enumerated_at: str,
    rank: int,
) -> dict[str, Any]:
    channel = CHANNELS[channel_id]
    host = str(record["normalized_host"]).casefold().rstrip(".")
    return {
        "schema_version": "target_text_candidate_v1",
        "candidate_id": f"TTCV1_CAND_{channel['candidate_prefix']}_{rank:03d}",
        "enumeration_wave_id": wave_id,
        "channel_id": channel_id,
        "channel_target_stratum": channel["stratum"],
        "predicted_artifact_type": "WEBSITE_SNAPSHOT",
        "reference": {
            "source_id": record["source_id"],
            "source_record_id": str(record["source_record_id"]),
            "source_url": record["reference_url"],
            "reference_role": channel["reference_role"],
            "reference_observed_at": record["reference_observed_at"],
            "reference_sha256": record["reference_sha256"],
        },
        "candidate_identity": {
            "entity_name_from_reference": record["entity_name_from_reference"],
            "candidate_url": record["candidate_url"],
            "normalized_host": host,
            "normalized_host_sha256": hashlib.sha256(host.encode("utf-8")).hexdigest(),
            "identity_linkage_basis": record["identity_linkage_basis"],
        },
        "enumerated_at": enumerated_at,
        "queue_state": "PROVENANCE_ENUMERATED_UNCAPTURED",
        "exclusion_screen": {
            "opened_normalized_host": "PASS",
            "opened_reference_identity": "PASS",
            "legacy_component": record["legacy_component"],
            "exact_capture": "PENDING_CAPTURE",
            "exact_text": "PENDING_CAPTURE",
            "case_campaign_entity_family": "PENDING_REVIEW",
            "near_duplicate": "PENDING_CAPTURE",
        },
        "capture_plan": {
            "capture_source": "WAYBACK_MACHINE",
            "live_candidate_domain_access_allowed": False,
            "automatic_external_redirect_following": False,
            "raw_capture_overwrite_allowed": False,
        },
        "review_state": {
            "artifact_capture": "MISSING",
            "identity_resolution": "UNRESOLVED",
            "ground_truth_status": "UNCERTAIN",
            "label_confidence": "LOW",
            "review_status": "UNREVIEWED",
            "primary_review": "NOT_STARTED",
            "independent_second_review": "NOT_STARTED",
            "owner_acceptance": "NOT_REQUESTED",
            "training_eligible": "NO",
            "label_created": False,
        },
        "safety": {
            "live_domain_accessed": False,
            "wayback_queried": False,
            "model_scored": False,
        },
    }


def enumerate_balanced_candidates(
    channel_records: dict[str, list[dict[str, Any]]],
    *,
    quotas: dict[str, int],
    seed: str,
    wave_id: str,
    enumerated_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a complete four-channel queue or fail without partial output."""
    if set(channel_records) != set(CHANNELS):
        raise ValueError("channel_records must contain exactly the four frozen channels")
    if set(quotas) != set(CHANNELS) or any(not isinstance(value, int) or value < 1 for value in quotas.values()):
        raise ValueError("quotas must contain positive integers for exactly the four frozen channels")
    if not re.fullmatch(r"TTCV1_ENUM_[A-Z0-9_-]+", wave_id):
        raise ValueError("invalid wave_id")
    if not enumerated_at:
        raise ValueError("enumerated_at must be explicitly frozen")

    exclusion_counts: dict[str, Counter[str]] = {channel: Counter() for channel in CHANNELS}
    eligible: dict[str, list[dict[str, Any]]] = {channel: [] for channel in CHANNELS}
    for channel_id, records in channel_records.items():
        seen_reference_ids: set[tuple[str, str]] = set()
        seen_hosts: set[str] = set()
        for record in records:
            errors = _validate_reference_record(channel_id, record)
            if errors:
                exclusion_counts[channel_id].update(errors)
                continue
            reference_key = (str(record["source_id"]), str(record["source_record_id"]))
            host = str(record["normalized_host"]).casefold().rstrip(".")
            if reference_key in seen_reference_ids:
                exclusion_counts[channel_id]["duplicate_reference_record"] += 1
                continue
            if host in seen_hosts:
                exclusion_counts[channel_id]["duplicate_host_within_channel"] += 1
                continue
            seen_reference_ids.add(reference_key)
            seen_hosts.add(host)
            normalized = dict(record)
            normalized["normalized_host"] = host
            eligible[channel_id].append(normalized)

    host_channels: defaultdict[str, set[str]] = defaultdict(set)
    entity_strata: defaultdict[str, set[str]] = defaultdict(set)
    for channel_id, records in eligible.items():
        for record in records:
            host_channels[str(record["normalized_host"])].add(channel_id)
            entity = _normalized_entity(record["entity_name_from_reference"])
            if entity:
                entity_strata[entity].add(str(CHANNELS[channel_id]["stratum"]))
    cross_channel_hosts = {host for host, channels in host_channels.items() if len(channels) > 1}
    cross_stratum_entities = {entity for entity, strata in entity_strata.items() if len(strata) > 1}
    for channel_id, records in eligible.items():
        filtered: list[dict[str, Any]] = []
        for record in records:
            if record["normalized_host"] in cross_channel_hosts:
                exclusion_counts[channel_id]["cross_channel_host_overlap"] += 1
                continue
            if _normalized_entity(record["entity_name_from_reference"]) in cross_stratum_entities:
                exclusion_counts[channel_id]["cross_stratum_entity_overlap"] += 1
                continue
            filtered.append(record)
        filtered.sort(key=lambda record: _stable_key(seed, channel_id, record))
        eligible[channel_id] = filtered

    shortfalls = {
        channel_id: {"eligible": len(eligible[channel_id]), "required": quotas[channel_id]}
        for channel_id in CHANNELS
        if len(eligible[channel_id]) < quotas[channel_id]
    }
    if shortfalls:
        raise ValueError(f"balanced enumeration shortfall; no queue emitted: {shortfalls}")

    queue: list[dict[str, Any]] = []
    selected_counts: dict[str, int] = {}
    for channel_id in CHANNELS:
        selected = eligible[channel_id][: quotas[channel_id]]
        selected_counts[channel_id] = len(selected)
        for rank, record in enumerate(selected, start=1):
            queue.append(
                _candidate_record(
                    channel_id,
                    record,
                    wave_id=wave_id,
                    enumerated_at=enumerated_at,
                    rank=rank,
                )
            )
    report = {
        "analysis_id": "ISI_TARGET_TEXT_CORPUS_V1_CANDIDATE_ENUMERATION",
        "status": "PROVENANCE_QUEUE_CREATED_CAPTURE_NOT_STARTED_LABELS_NOT_CREATED",
        "wave_id": wave_id,
        "selection_seed": seed,
        "input_counts": {channel: len(channel_records[channel]) for channel in CHANNELS},
        "eligible_pool_counts": {channel: len(eligible[channel]) for channel in CHANNELS},
        "selected_counts": selected_counts,
        "selected_total": len(queue),
        "exclusion_counts": {
            channel: dict(sorted(counts.items())) for channel, counts in exclusion_counts.items()
        },
        "cross_channel_host_overlap_count": len(cross_channel_hosts),
        "cross_stratum_entity_overlap_count": len(cross_stratum_entities),
        "readiness": {
            "independent_provenance_qa_complete": False,
            "queue_hash_registered": False,
            "capture_allowed": False,
            "labels_created": 0,
            "training_eligible_records": 0,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "new_artifact_captures": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
        },
    }
    return queue, report
