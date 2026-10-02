"""Build provenance-only source inventory and opened-cohort exclusion index."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify_hash(path: Path, expected: object) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch for {path}: {actual} != {expected}")


def select_role(container: object, role: str) -> dict[str, Any]:
    if not isinstance(container, list):
        raise ValueError(f"Expected list container for artifact role {role}")
    matches = [item for item in container if item.get("role") == role]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one artifact with role {role}; found {len(matches)}")
    return matches[0]


def normalized_original_host(artifact: dict[str, Any]) -> str:
    host = str(artifact.get("candidate_host") or "").strip().lower()
    if not host:
        url = str(artifact.get("url") or "").strip()
        replay = re.search(r"https?://web\.archive\.org/web/[^/]+/(https?://.+)$", url)
        target_url = replay.group(1) if replay else url
        host = (urlparse(target_url).hostname or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError(f"Invalid domain host: {host!r}") from exc
    return host


def normalized_url_hash(artifact: dict[str, Any]) -> str | None:
    url = str(artifact.get("url") or "").strip()
    if not url:
        return None
    return sha256_bytes(url.encode("utf-8"))


def collision_groups(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in records:
        value = record.get(key)
        if value:
            grouped[str(value)].append(str(record["record_exclusion_key"]))
    return [
        {key: value, "members": sorted(members)}
        for value, members in sorted(grouped.items())
        if len(members) > 1
    ]


def build_candidate_inventory(protocol: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    source_by_id = {item["source_id"]: item for item in sources["sources"]}
    channels: list[dict[str, Any]] = []
    missing_source_ids: list[str] = []
    for channel in protocol["candidate_channels"]:
        resolved_sources = []
        for source_id in channel["registered_source_ids"]:
            source = source_by_id.get(source_id)
            if source is None:
                missing_source_ids.append(source_id)
                continue
            resolved_sources.append(
                {
                    key: source[key]
                    for key in (
                        "source_id",
                        "tier",
                        "name",
                        "url",
                        "source_type",
                        "default_evidence_level",
                        "raw_label_semantics",
                        "allowed_uses",
                        "gold_eligible",
                    )
                }
            )
        channels.append({**channel, "resolved_sources": resolved_sources})

    ready_counts: dict[str, int] = defaultdict(int)
    planned_counts: dict[str, int] = defaultdict(int)
    for channel in channels:
        status = channel["planned_target_status"]
        planned_counts[status] += 1
        if channel["readiness"] == "READY_FOR_PROVENANCE_ENUMERATION_ONLY":
            ready_counts[status] += 1

    return {
        "inventory_id": "ISI_TARGET_TEXT_CORPUS_V1_CANDIDATE_SOURCE_INVENTORY",
        "status": "FROZEN_PROVENANCE_ONLY_WITH_CHANNEL_GAPS",
        "protocol_id": protocol["protocol_id"],
        "source_registry": next(
            item for item in protocol["inputs"] if item["role"] == "source_registry"
        ),
        "record_count": 0,
        "channels": channels,
        "non_candidate_sources": protocol["non_candidate_sources"],
        "coverage": {
            "planned_channels_by_target_status": dict(sorted(planned_counts.items())),
            "provenance_enumeration_ready_channels_by_target_status": dict(
                sorted(ready_counts.items())
            ),
            "minimum_required_channels_per_target_status": 2,
            "channel_gate_passed": all(ready_counts.get(key, 0) >= 2 for key in ("CONFIRMED", "LEGITIMATE")),
            "missing_registered_source_ids": sorted(set(missing_source_ids)),
        },
        "open_gaps": [
            "The corroborated case-seed channel lacks a frozen corroboration and artifact-capture source protocol.",
            "The legitimate post/message channel lacks a registered platform source and terms-reviewed immutable capture protocol.",
            "No candidate record may be enumerated or captured until the opened-cohort exclusion index and legacy grouping remediation verify.",
        ],
        "safety_contract": {
            **protocol["safety_contract"],
            "candidate_records_enumerated": 0,
            "artifact_text_emitted": 0,
        },
    }


def build_exclusion_index(protocol: dict[str, Any], root: Path) -> dict[str, Any]:
    cohort_summaries: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for cohort in protocol["opened_cohorts"]:
        registry_path = resolve(root, cohort["registry_path"])
        verify_hash(registry_path, cohort["registry_sha256"])
        registry = load_json(registry_path)
        artifact_entry = select_role(
            registry.get(cohort["artifact_container"]), cohort["artifact_role"]
        )
        artifact_path = resolve(root, artifact_entry["path"])
        verify_hash(artifact_path, artifact_entry["sha256"])
        artifact_data = load_json(artifact_path)
        cohort_records = artifact_data.get("records")
        if not isinstance(cohort_records, list):
            raise ValueError(f"Missing records list: {artifact_path}")
        if len(cohort_records) != cohort["expected_record_count"]:
            raise ValueError(f"Unexpected record count: {artifact_path}")

        cohort_summaries.append(
            {
                "cohort_id": cohort["cohort_id"],
                "registry_path": cohort["registry_path"],
                "registry_sha256": cohort["registry_sha256"],
                "artifact_path": str(artifact_entry["path"]),
                "artifact_sha256": artifact_entry["sha256"],
                "record_count": len(cohort_records),
            }
        )

        for raw_record in cohort_records:
            artifact = raw_record.get("artifact", {})
            if not isinstance(artifact, dict):
                raise ValueError("Artifact metadata must be an object")
            cohort_record_id = raw_record.get("case_id") or raw_record.get(
                "benchmark_record_id"
            )
            if not cohort_record_id:
                raise ValueError(f"Missing cohort record ID in {cohort['cohort_id']}")
            capture_sha256 = artifact.get("source_capture_sha256") or artifact.get(
                "capture_sha256"
            )
            text_sha256 = artifact.get("text_sha256")
            host = normalized_original_host(artifact)
            if not capture_sha256 or not text_sha256 or not host:
                raise ValueError(f"Incomplete exclusion metadata: {cohort_record_id}")
            review_provenance = raw_record.get("review_provenance", {})
            source_candidate_id = (
                review_provenance.get("source_candidate_id")
                if isinstance(review_provenance, dict)
                else None
            )
            record_key = f"{cohort['cohort_id']}::{cohort_record_id}"
            records.append(
                {
                    "record_exclusion_key": record_key,
                    "cohort_id": cohort["cohort_id"],
                    "cohort_record_id": cohort_record_id,
                    "case_id": raw_record.get("case_id"),
                    "case_or_campaign_group_id": raw_record.get(
                        "case_or_campaign_group_id"
                    ),
                    "near_duplicate_group_id": raw_record.get(
                        "near_duplicate_group_id"
                    ),
                    "artifact_id": artifact.get("artifact_id"),
                    "source_record_id": artifact.get("source_record_id"),
                    "source_candidate_id": source_candidate_id,
                    "capture_sha256": capture_sha256,
                    "text_sha256": text_sha256,
                    "exact_text_group_key": f"EXACT_TEXT::{text_sha256}",
                    "normalized_host_sha256": sha256_bytes(host.encode("utf-8")),
                    "url_sha256": normalized_url_hash(artifact),
                    "legacy_case_id_missing": raw_record.get("case_id") is None,
                    "legacy_group_identifiers_missing": not bool(
                        raw_record.get("case_or_campaign_group_id")
                        and raw_record.get("near_duplicate_group_id")
                    ),
                }
            )

    records.sort(key=lambda item: item["record_exclusion_key"])
    unique_record_keys = {item["record_exclusion_key"] for item in records}
    if len(unique_record_keys) != len(records):
        raise ValueError("Duplicate record exclusion key")

    counts = {
        "cohorts": len(cohort_summaries),
        "opened_records": len(records),
        "unique_record_exclusion_keys": len(unique_record_keys),
        "records_with_case_id": sum(item["case_id"] is not None for item in records),
        "records_missing_case_id": sum(item["case_id"] is None for item in records),
        "records_with_case_or_campaign_group_id": sum(
            item["case_or_campaign_group_id"] is not None for item in records
        ),
        "records_with_near_duplicate_group_id": sum(
            item["near_duplicate_group_id"] is not None for item in records
        ),
        "records_with_source_candidate_id": sum(
            item["source_candidate_id"] is not None for item in records
        ),
        "unique_capture_sha256": len({item["capture_sha256"] for item in records}),
        "unique_text_sha256": len({item["text_sha256"] for item in records}),
        "unique_normalized_host_sha256": len(
            {item["normalized_host_sha256"] for item in records}
        ),
    }
    capture_collisions = collision_groups(records, "capture_sha256")
    text_collisions = collision_groups(records, "text_sha256")
    host_collisions = collision_groups(records, "normalized_host_sha256")

    return {
        "index_id": "ISI_TARGET_TEXT_CORPUS_V1_OPENED_EXTERNAL_EXCLUSION_INDEX",
        "status": "FROZEN_EXACT_AND_DOMAIN_COMPLETE_LEGACY_GROUP_GAPS_OPEN",
        "protocol_id": protocol["protocol_id"],
        "cohorts": cohort_summaries,
        "counts": counts,
        "records": records,
        "collision_groups": {
            "capture_sha256": capture_collisions,
            "text_sha256": text_collisions,
            "normalized_host_sha256": host_collisions,
        },
        "quality_gates": {
            "all_opened_cohorts_hash_verified": True,
            "every_opened_record_has_capture_sha256": all(
                bool(item["capture_sha256"]) for item in records
            ),
            "every_opened_record_has_text_sha256": all(
                bool(item["text_sha256"]) for item in records
            ),
            "every_opened_record_has_normalized_host_exclusion_key": all(
                bool(item["normalized_host_sha256"]) for item in records
            ),
            "every_available_case_and_group_identifier_preserved": True,
            "missing_legacy_case_or_group_identifiers_reported": True,
            "artifact_text_emitted": False,
            "ground_truth_status_emitted_per_record": False,
            "exact_and_normalized_host_exclusion_ready": True,
            "case_domain_family_and_normalized_near_duplicate_exclusion_ready": False,
        },
        "open_gaps": [
            "Legacy benchmark V1/V2/V3 records do not contain formal case_id, case/campaign group, or near-duplicate group fields.",
            "Exact capture, exact text, and normalized-host exclusions are complete, but registrable-domain-family mapping, legacy case mapping, and normalized near-duplicate review must be completed before new candidate capture.",
        ],
        "safety_contract": {
            **protocol["safety_contract"],
            "existing_opened_records_processed_offline": len(records),
            "artifact_text_emitted": 0,
            "ground_truth_statuses_emitted": 0,
        },
    }


def build(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    if protocol.get("status") != "LOCKED_BEFORE_OFFLINE_METADATA_DERIVATION":
        raise ValueError("Protocol is not locked")
    for item in protocol["inputs"]:
        verify_hash(resolve(root, item["path"]), item["sha256"])

    sources_item = next(item for item in protocol["inputs"] if item["role"] == "source_registry")
    sources = load_json(resolve(root, sources_item["path"]))
    inventory = build_candidate_inventory(protocol, sources)
    exclusion_index = build_exclusion_index(protocol, root)

    output_paths = {
        role: resolve(root, path) for role, path in protocol["output_paths"].items()
    }
    for path in output_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    output_paths["candidate_source_inventory"].write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output_paths["opened_external_exclusion_index"].write_text(
        json.dumps(exclusion_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "protocol_id": protocol["protocol_id"],
        "candidate_source_inventory": {
            "path": str(output_paths["candidate_source_inventory"]),
            "sha256": sha256_file(output_paths["candidate_source_inventory"]),
            "record_count": inventory["record_count"],
            "channel_gate_passed": inventory["coverage"]["channel_gate_passed"],
        },
        "opened_external_exclusion_index": {
            "path": str(output_paths["opened_external_exclusion_index"]),
            "sha256": sha256_file(output_paths["opened_external_exclusion_index"]),
            "record_count": exclusion_index["counts"]["opened_records"],
            "exact_and_normalized_host_exclusion_ready": exclusion_index["quality_gates"][
                "exact_and_normalized_host_exclusion_ready"
            ],
            "case_domain_family_and_normalized_near_duplicate_exclusion_ready": exclusion_index[
                "quality_gates"
            ]["case_domain_family_and_normalized_near_duplicate_exclusion_ready"],
        },
        "network_operations": 0,
        "new_records_acquired": 0,
        "labels_created": 0,
        "model_fit_operations": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "configs" / "target_text_corpus_v1_preacquisition_protocol.json",
    )
    args = parser.parse_args()
    print(json.dumps(build(args.protocol), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
