"""Build deterministic exclusion-only groups for legacy opened-cohort records."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected object at {path}:{line_number}")
        rows.append(value)
    return rows


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify_hash(path: Path, expected: object) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise ValueError(f"Artifact missing or changed: {path}")


def canonical_record_sha256(record: dict[str, Any]) -> str:
    payload = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


class UnionFind:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, first: str, second: str) -> None:
        left = self.find(first)
        right = self.find(second)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def build_components(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    keys = [str(item["record_exclusion_key"]) for item in records]
    union_find = UnionFind(keys)
    for field in ("capture_sha256", "text_sha256", "normalized_host_sha256"):
        seen: dict[str, str] = {}
        for record in records:
            value = str(record[field])
            key = str(record["record_exclusion_key"])
            if value in seen:
                union_find.union(key, seen[value])
            else:
                seen[value] = key
    components: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        components[union_find.find(key)].append(key)
    return {
        root: sorted(members) for root, members in sorted(components.items())
    }


def group_id(members: list[str]) -> str:
    digest = sha256_bytes("\n".join(sorted(members)).encode("utf-8"))
    return f"LEGX_{digest[:16].upper()}"


def build(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    if protocol.get("status") != "LOCKED_BEFORE_REMEDIATION_MAP_BUILD":
        raise ValueError("Protocol is not locked")
    inputs = {item["role"]: item for item in protocol["inputs"]}
    for item in inputs.values():
        verify_hash(resolve(root, item["path"]), item["sha256"])

    exclusion_index = load_json(
        resolve(root, inputs["opened_external_exclusion_index"]["path"])
    )
    opened_records = exclusion_index["records"]
    if len(opened_records) != protocol["expected_counts"]["opened_records"]:
        raise ValueError("Opened record count changed")

    queue_by_candidate_id: dict[str, tuple[str, dict[str, Any]]] = {}
    queue_roles = [
        "matched_wayback_v1_candidate_queue",
        "matched_wayback_v1_supplement_queue",
        "wayback_language_v2_candidate_queue",
        "wayback_holdout_v3_candidate_queue",
    ]
    for role in queue_roles:
        for queue_record in load_jsonl(resolve(root, inputs[role]["path"])):
            candidate_id = str(queue_record.get("candidate_id") or "")
            if not candidate_id:
                raise ValueError(f"Missing candidate_id in {role}")
            if candidate_id in queue_by_candidate_id:
                raise ValueError(f"Duplicate candidate_id across queues: {candidate_id}")
            queue_by_candidate_id[candidate_id] = (role, queue_record)

    components = build_components(opened_records)
    component_by_member = {
        member: members for members in components.values() for member in members
    }
    record_by_key = {item["record_exclusion_key"]: item for item in opened_records}
    legacy_records = [item for item in opened_records if item["legacy_case_id_missing"]]
    remediated: list[dict[str, Any]] = []

    for record in legacy_records:
        source_candidate_id = record.get("source_candidate_id")
        queue_match = queue_by_candidate_id.get(str(source_candidate_id))
        if queue_match is None:
            raise ValueError(
                f"No exact queue join for {record['record_exclusion_key']}: {source_candidate_id}"
            )
        queue_role, queue_record = queue_match
        members = component_by_member[record["record_exclusion_key"]]
        component_records = [record_by_key[key] for key in members]
        anchor_case_ids = sorted(
            {
                str(item["case_id"])
                for item in component_records
                if item.get("case_id") is not None
            }
        )
        anchor_case_groups = sorted(
            {
                str(item["case_or_campaign_group_id"])
                for item in component_records
                if item.get("case_or_campaign_group_id") is not None
            }
        )
        anchor_near_groups = sorted(
            {
                str(item["near_duplicate_group_id"])
                for item in component_records
                if item.get("near_duplicate_group_id") is not None
            }
        )
        shared_link_types = []
        for field, label in (
            ("capture_sha256", "EXACT_CAPTURE_SHA256"),
            ("text_sha256", "EXACT_TEXT_SHA256"),
            ("normalized_host_sha256", "EXACT_NORMALIZED_HOST_SHA256"),
        ):
            if sum(item[field] == record[field] for item in component_records) > 1:
                shared_link_types.append(label)

        remediated.append(
            {
                "record_exclusion_key": record["record_exclusion_key"],
                "cohort_id": record["cohort_id"],
                "cohort_record_id": record["cohort_record_id"],
                "source_candidate_id": source_candidate_id,
                "source_queue_role": queue_role,
                "source_queue_record_sha256": canonical_record_sha256(queue_record),
                "upstream_source_id": queue_record.get("source_id"),
                "upstream_source_case_id": queue_record.get("source_case_id"),
                "upstream_source_record_id": queue_record.get("source_record_id"),
                "legacy_exclusion_group_id": group_id(members),
                "component_record_count": len(members),
                "component_member_keys": members,
                "shared_exact_link_types": shared_link_types,
                "anchor_case_ids": anchor_case_ids,
                "anchor_case_or_campaign_group_ids": anchor_case_groups,
                "anchor_near_duplicate_group_ids": anchor_near_groups,
                "remediation_status": (
                    "ANCHORED_TO_FROZEN_OPENED_CASE_BY_EXACT_METADATA"
                    if anchor_case_ids
                    else "LEGACY_EXCLUSION_ONLY_UNANCHORED"
                ),
                "formal_case_id_created": False,
                "eligible_as_evidence_backed_case_mapping": False,
                "manual_cross_domain_case_review_required": True,
            }
        )

    remediated.sort(key=lambda item: item["record_exclusion_key"])
    anchored = sum(bool(item["anchor_case_ids"]) for item in remediated)
    counts = {
        "opened_records": len(opened_records),
        "legacy_records": len(legacy_records),
        "queue_joined_legacy_records": len(remediated),
        "all_components": len(components),
        "legacy_components": len(
            {item["legacy_exclusion_group_id"] for item in remediated}
        ),
        "legacy_records_anchored_to_existing_case": anchored,
        "legacy_records_unanchored_exclusion_only": len(remediated) - anchored,
        "formal_case_ids_created": 0,
        "labels_created": 0,
    }
    if counts != protocol["expected_counts"]:
        raise ValueError(f"Remediation counts changed: {counts}")

    output = {
        "map_id": "ISI_TARGET_TEXT_CORPUS_V1_LEGACY_GROUP_REMEDIATION_MAP_V1",
        "status": "FROZEN_EXCLUSION_GROUPS_ASSIGNED_CASE_LINKAGE_PARTIAL",
        "protocol_id": protocol["protocol_id"],
        "input_exclusion_index": inputs["opened_external_exclusion_index"],
        "queue_inputs": [inputs[role] for role in queue_roles],
        "grouping_algorithm": protocol["grouping_algorithm"],
        "counts": counts,
        "records": remediated,
        "quality_gates": {
            "every_legacy_record_joined_to_frozen_queue": True,
            "every_legacy_record_has_exclusion_group": True,
            "formal_case_ids_backfilled": False,
            "evidence_backed_case_linkage_complete": anchored == len(remediated),
            "artifact_text_emitted": False,
            "ground_truth_status_emitted": False,
            "independent_review_complete": False,
            "new_candidate_capture_allowed": False,
        },
        "interpretation": {
            "anchored_group": "Exact metadata connects the legacy benchmark record to an opened record with a frozen case ID; this is an exclusion linkage, not a new label review.",
            "unanchored_group": "The record receives a deterministic exclusion-only group and retains upstream queue provenance; it is not an evidence-backed real-world case mapping.",
        },
        "safety_contract": {
            **protocol["safety_contract"],
            "existing_opened_records_processed_offline": len(opened_records),
            "legacy_records_remediated": len(remediated),
            "artifact_text_emitted": 0,
            "ground_truth_statuses_emitted": 0,
        },
    }
    output_path = resolve(root, protocol["outputs"]["remediation_map"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "protocol_id": protocol["protocol_id"],
        "output_path": str(output_path),
        "output_sha256": sha256_file(output_path),
        "counts": counts,
        "network_operations": 0,
        "formal_case_ids_created": 0,
        "labels_created": 0,
        "model_fit_operations": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT
        / "configs"
        / "target_text_corpus_v1_legacy_group_remediation_v1.json",
    )
    args = parser.parse_args()
    print(json.dumps(build(args.protocol), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

