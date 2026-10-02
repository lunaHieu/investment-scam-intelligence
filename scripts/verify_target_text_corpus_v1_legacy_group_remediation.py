"""Independently recompute and verify the legacy exclusion-group remediation map."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_LEGACY_GROUP_REMEDIATION_V1"
REGISTRY_STATUS = "FROZEN_INDEPENDENT_REVIEW_PASS_CAPTURE_BLOCKED"


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
    rows: list[dict[str, Any]] = []
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


def canonical_record_sha256(record: dict[str, Any]) -> str:
    encoded = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def independently_recompute_components(
    records: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Use bucket adjacency plus BFS, independently of the builder's union-find."""
    keys = [str(item["record_exclusion_key"]) for item in records]
    record_by_key = {str(item["record_exclusion_key"]): item for item in records}
    buckets: dict[tuple[str, str], set[str]] = defaultdict(set)
    fields = ("capture_sha256", "text_sha256", "normalized_host_sha256")
    for record in records:
        key = str(record["record_exclusion_key"])
        for field in fields:
            buckets[(field, str(record[field]))].add(key)

    remaining = set(keys)
    components: dict[str, list[str]] = {}
    while remaining:
        seed = min(remaining)
        queue = deque([seed])
        component: set[str] = set()
        while queue:
            key = queue.popleft()
            if key in component:
                continue
            component.add(key)
            record = record_by_key[key]
            for field in fields:
                for neighbor in buckets[(field, str(record[field]))]:
                    if neighbor not in component:
                        queue.append(neighbor)
        remaining.difference_update(component)
        components[seed] = sorted(component)
    return components


def component_id(members: list[str]) -> str:
    digest = sha256_bytes("\n".join(sorted(members)).encode("utf-8"))
    return f"LEGX_{digest[:16].upper()}"


def independent_review(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    errors: list[str] = []
    inputs = {item["role"]: item for item in protocol["inputs"]}
    for role, item in inputs.items():
        path = resolve(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"Input missing or changed: {role}")

    index_path = resolve(root, inputs["opened_external_exclusion_index"]["path"])
    map_path = resolve(root, protocol["outputs"]["remediation_map"])
    if not index_path.is_file() or not map_path.is_file():
        errors.append("Index or remediation map unavailable")
        return {
            "review_id": "ISI_TARGET_TEXT_CORPUS_V1_LEGACY_GROUP_INDEPENDENT_REVIEW_V1",
            "status": "FAIL",
            "valid": False,
            "errors": errors,
        }

    exclusion_index = load_json(index_path)
    remediation_map = load_json(map_path)
    opened_records = exclusion_index.get("records", [])
    legacy_records = [item for item in opened_records if item.get("legacy_case_id_missing")]
    record_by_key = {item["record_exclusion_key"]: item for item in opened_records}

    queue_roles = [
        "matched_wayback_v1_candidate_queue",
        "matched_wayback_v1_supplement_queue",
        "wayback_language_v2_candidate_queue",
        "wayback_holdout_v3_candidate_queue",
    ]
    queue_by_candidate: dict[str, tuple[str, dict[str, Any]]] = {}
    for role in queue_roles:
        for row in load_jsonl(resolve(root, inputs[role]["path"])):
            candidate_id = str(row.get("candidate_id") or "")
            if not candidate_id or candidate_id in queue_by_candidate:
                errors.append(f"Invalid or duplicate queue candidate: {candidate_id}")
            else:
                queue_by_candidate[candidate_id] = (role, row)

    components = independently_recompute_components(opened_records)
    component_by_member = {
        member: members for members in components.values() for member in members
    }
    expected_records: list[dict[str, Any]] = []
    for record in legacy_records:
        source_candidate_id = str(record.get("source_candidate_id") or "")
        queue_match = queue_by_candidate.get(source_candidate_id)
        if queue_match is None:
            errors.append(f"Missing queue join: {record['record_exclusion_key']}")
            continue
        queue_role, queue_record = queue_match
        members = component_by_member[record["record_exclusion_key"]]
        component_records = [record_by_key[key] for key in members]
        anchor_cases = sorted(
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
        shared_links = []
        for field, label in (
            ("capture_sha256", "EXACT_CAPTURE_SHA256"),
            ("text_sha256", "EXACT_TEXT_SHA256"),
            ("normalized_host_sha256", "EXACT_NORMALIZED_HOST_SHA256"),
        ):
            if sum(item[field] == record[field] for item in component_records) > 1:
                shared_links.append(label)
        expected_records.append(
            {
                "record_exclusion_key": record["record_exclusion_key"],
                "cohort_id": record["cohort_id"],
                "cohort_record_id": record["cohort_record_id"],
                "source_candidate_id": record.get("source_candidate_id"),
                "source_queue_role": queue_role,
                "source_queue_record_sha256": canonical_record_sha256(queue_record),
                "upstream_source_id": queue_record.get("source_id"),
                "upstream_source_case_id": queue_record.get("source_case_id"),
                "upstream_source_record_id": queue_record.get("source_record_id"),
                "legacy_exclusion_group_id": component_id(members),
                "component_record_count": len(members),
                "component_member_keys": members,
                "shared_exact_link_types": shared_links,
                "anchor_case_ids": anchor_cases,
                "anchor_case_or_campaign_group_ids": anchor_case_groups,
                "anchor_near_duplicate_group_ids": anchor_near_groups,
                "remediation_status": (
                    "ANCHORED_TO_FROZEN_OPENED_CASE_BY_EXACT_METADATA"
                    if anchor_cases
                    else "LEGACY_EXCLUSION_ONLY_UNANCHORED"
                ),
                "formal_case_id_created": False,
                "eligible_as_evidence_backed_case_mapping": False,
                "manual_cross_domain_case_review_required": True,
            }
        )
    expected_records.sort(key=lambda item: item["record_exclusion_key"])
    actual_records = remediation_map.get("records", [])
    if actual_records != expected_records:
        errors.append("Per-record remediation map differs from independent recomputation")

    expected_counts = protocol["expected_counts"]
    if remediation_map.get("counts") != expected_counts:
        errors.append("Remediation counts differ from frozen protocol")
    if len(components) != expected_counts["all_components"]:
        errors.append("Independent component count changed")
    if len(expected_records) != expected_counts["legacy_records"]:
        errors.append("Independent legacy-record count changed")
    serialized_records = json.dumps(actual_records, ensure_ascii=False)
    if (
        "ground_truth_status" in serialized_records
        or "visible_text" in serialized_records
        or '"text"' in serialized_records
    ):
        errors.append("Artifact text or ground-truth status leaked into remediation records")
    if any(item.get("formal_case_id_created") is not False for item in actual_records):
        errors.append("A formal case ID was created")
    if any(
        item.get("eligible_as_evidence_backed_case_mapping") is not False
        for item in actual_records
    ):
        errors.append("A technical exclusion group was promoted to evidence-backed mapping")

    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_LEGACY_GROUP_INDEPENDENT_REVIEW_V1",
        "status": "INDEPENDENT_OFFLINE_RECOMPUTATION_PASS" if not errors else "FAIL",
        "valid": not errors,
        "protocol_path": str(protocol_path),
        "protocol_sha256": sha256_file(protocol_path),
        "remediation_map_path": str(map_path),
        "remediation_map_sha256": sha256_file(map_path),
        "builder_module_imported": False,
        "opened_records_recomputed": len(opened_records),
        "legacy_records_compared": len(expected_records),
        "queue_joins_recomputed": len(expected_records),
        "components_recomputed": len(components),
        "anchored_legacy_records": sum(
            bool(item["anchor_case_ids"]) for item in expected_records
        ),
        "unanchored_exclusion_only_records": sum(
            not bool(item["anchor_case_ids"]) for item in expected_records
        ),
        "formal_case_ids_created": 0,
        "labels_created": 0,
        "artifact_text_emitted": 0,
        "ground_truth_statuses_emitted": 0,
        "network_operations": 0,
        "new_candidate_capture_allowed": False,
        "errors": errors,
    }


def verify_registry(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    role_paths: dict[str, Path] = {}
    checked: list[dict[str, object]] = []
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != REGISTRY_STATUS:
        errors.append("Unexpected registry status")
    for item in (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    ):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual_hash = sha256_file(path) if path.is_file() else None
        if role in role_paths:
            errors.append(f"Duplicate artifact role: {role}")
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual_hash})
        if actual_hash != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")

    protocol_path = role_paths.get("remediation_protocol")
    stored_review_path = role_paths.get("independent_review")
    recomputed: dict[str, Any] = {}
    if protocol_path is None:
        errors.append("Remediation protocol missing")
    else:
        recomputed = independent_review(protocol_path)
        if not recomputed.get("valid"):
            errors.extend(f"Independent review: {item}" for item in recomputed["errors"])
    if stored_review_path is None or not stored_review_path.is_file():
        errors.append("Stored independent review missing")
    elif load_json(stored_review_path) != recomputed:
        errors.append("Stored independent review differs from recomputation")

    safety = registry.get("safety_contract", {})
    expected_safety = {
        "network_operations": 0,
        "domain_access_allowed": False,
        "new_records_acquired": 0,
        "new_artifact_captures": 0,
        "formal_case_ids_created": 0,
        "labels_created": 0,
        "labels_changed": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "validation_or_test_openings": 0,
        "training_allowed": False,
        "deployment_allowed": False,
        "existing_opened_records_processed_offline": 107,
        "legacy_records_remediated": 86,
        "artifact_text_emitted": 0,
        "ground_truth_statuses_emitted": 0,
    }
    if safety != expected_safety:
        errors.append("Registry safety contract changed")

    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "legacy_records_remediated": recomputed.get("legacy_records_compared"),
        "anchored_legacy_records": recomputed.get("anchored_legacy_records"),
        "unanchored_exclusion_only_records": recomputed.get(
            "unanchored_exclusion_only_records"
        ),
        "independent_review_passed": recomputed.get("valid", False),
        "capture_allowed": False,
        "model_fit_operations": 0,
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--protocol", type=Path)
    mode.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.protocol is not None:
        result = independent_review(args.protocol)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    else:
        if args.output is not None:
            parser.error("--output is only valid with --protocol")
        result = verify_registry(args.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

