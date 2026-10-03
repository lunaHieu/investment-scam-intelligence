"""Independently verify the complete Wayback availability result V2."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.query_target_text_corpus_v1_wayback_availability import (
    load_json,
    load_jsonl,
    normalize_snapshot_url,
    sha256_file,
)


EXPECTED_CHANNEL_TOTALS = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": 10,
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": 10,
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": 10,
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": 10,
}
EXPECTED_AVAILABLE_BY_CHANNEL = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": 5,
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": 7,
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": 8,
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": 9,
}
ANALYSIS_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_RESULT_V2"
EXPECTED_REGISTRY_STATUS = "FROZEN_COMPLETE_40_RESOLVED_29_AVAILABLE_CAPTURE_PLAN_BLOCKED"
EXPECTED_REGISTRY_SAFETY = {
    "network_operations": 0,
    "historical_availability_network_operations_registered": 41,
    "domain_access_allowed": False,
    "candidate_domain_access_operations": 0,
    "archived_page_download_operations": 0,
    "candidate_artifact_captures": 0,
    "labels_created": 0,
    "labels_changed": 0,
    "model_fit_operations": 0,
    "model_scoring_operations": 0,
    "validation_or_test_openings": 0,
    "training_allowed": False,
    "deployment_allowed": False,
}


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify(
    *, queue_path: Path, v1_path: Path, v2_path: Path
) -> dict[str, Any]:
    queue = load_jsonl(queue_path)
    v1 = load_json(v1_path)
    v2 = load_json(v2_path)
    errors: list[str] = []
    if v1.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_REPORT_V1":
        errors.append("Unexpected V1 report ID")
    if v2.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_REPORT_V2":
        errors.append("Unexpected V2 report ID")
    if v2.get("status") != "COMPLETE" or v2.get("capture_planning_ready") is not True:
        errors.append("V2 availability report is not complete")
    if v2.get("queue_sha256") != sha256_file(queue_path):
        errors.append("V2 queue hash mismatch")
    if v2.get("parent_report_sha256") != sha256_file(v1_path):
        errors.append("V2 parent-report hash mismatch")
    if v2.get("requested_candidate_count") != 40:
        errors.append("V2 must contain 40 candidate results")
    if v2.get("resolved_results_reused_from_v1") != 9:
        errors.append("V2 resolved-result reuse count changed")
    if v2.get("retry_candidate_count") != 31:
        errors.append("V2 retry candidate count changed")
    if v2.get("network_request_count_this_attempt") != 31:
        errors.append("V2 network request count changed")
    if v2.get("cumulative_network_request_count") != 41:
        errors.append("V2 cumulative request count changed")
    if v2.get("unresolved_error_count") != 0 or v2.get("stopped_on_http_429") is not False:
        errors.append("V2 retains an unresolved error or rate-limit stop")

    queue_by_id = {str(row["candidate_id"]): row for row in queue}
    v1_by_id = {str(row["candidate_id"]): row for row in v1.get("results", [])}
    v2_by_id = {str(row["candidate_id"]): row for row in v2.get("results", [])}
    if len(queue_by_id) != 40 or len(v1_by_id) != 40 or len(v2_by_id) != 40:
        errors.append("Queue or availability report contains missing/duplicate IDs")
    if set(queue_by_id) != set(v1_by_id) or set(queue_by_id) != set(v2_by_id):
        errors.append("Candidate membership changed across queue/V1/V2")

    prior_resolved = {candidate_id for candidate_id, row in v1_by_id.items() if row.get("error") is None}
    prior_unresolved = set(v1_by_id) - prior_resolved
    retry_ids = [str(value) for value in v2.get("retried_candidate_ids", [])]
    if set(retry_ids) != prior_unresolved or len(retry_ids) != len(prior_unresolved):
        errors.append("V2 retried a resolved row or omitted an unresolved row")
    for candidate_id in prior_resolved:
        if canonical(v1_by_id[candidate_id]) != canonical(v2_by_id[candidate_id]):
            errors.append(f"Resolved V1 result changed in V2: {candidate_id}")

    for candidate_id, result in v2_by_id.items():
        source = queue_by_id.get(candidate_id, {})
        identity = source.get("candidate_identity", {})
        expected = {
            "channel_id": source.get("channel_id"),
            "channel_target_stratum": source.get("channel_target_stratum"),
            "candidate_host": identity.get("normalized_host"),
            "candidate_url": identity.get("candidate_url"),
        }
        for key, value in expected.items():
            if result.get(key) != value:
                errors.append(f"Queue/result mismatch for {candidate_id}: {key}")
        if result.get("error") is not None or result.get("available") not in {True, False}:
            errors.append(f"Unresolved V2 result: {candidate_id}")
        if result.get("available") is True:
            try:
                normalized = normalize_snapshot_url(str(result.get("snapshot_url") or ""))
            except ValueError as error:
                errors.append(f"Invalid snapshot URL for {candidate_id}: {error}")
            else:
                if normalized != result.get("snapshot_url"):
                    errors.append(f"Snapshot URL is not HTTPS-normalized: {candidate_id}")
            if result.get("snapshot_http_status") != "200":
                errors.append(f"Available snapshot lacks HTTP 200: {candidate_id}")
        elif any(result.get(key) is not None for key in (
            "snapshot_timestamp", "snapshot_url", "snapshot_http_status"
        )):
            errors.append(f"Unavailable row retains snapshot evidence: {candidate_id}")

    channel_totals = Counter(str(row.get("channel_id")) for row in v2_by_id.values())
    available_by_channel = Counter(
        str(row.get("channel_id"))
        for row in v2_by_id.values()
        if row.get("available") is True
    )
    if dict(channel_totals) != EXPECTED_CHANNEL_TOTALS:
        errors.append(f"V2 channel totals changed: {dict(channel_totals)}")
    if dict(available_by_channel) != EXPECTED_AVAILABLE_BY_CHANNEL:
        errors.append(f"V2 available-by-channel counts changed: {dict(available_by_channel)}")
    if v2.get("available_snapshot_count") != 29 or v2.get("unavailable_snapshot_count") != 11:
        errors.append("V2 aggregate availability counts changed")
    safety = v2.get("safety_contract", {})
    expected_safety = {
        "candidate_live_domain_access_operations": 0,
        "only_archive_availability_hosts_accessed": True,
        "archived_page_download_operations": 0,
        "candidate_artifact_captures": 0,
        "labels_created": 0,
        "model_operations": 0,
        "training_allowed": False,
    }
    if safety != expected_safety:
        errors.append("V2 safety contract changed")
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_INDEPENDENT_QA_V2",
        "status": "PASS_40_RESOLVED_29_AVAILABLE_CAPTURE_PLAN_BLOCKED" if not errors else "FAIL",
        "inputs": {
            "queue": {"path": str(queue_path), "sha256": sha256_file(queue_path)},
            "availability_v1": {"path": str(v1_path), "sha256": sha256_file(v1_path)},
            "availability_v2": {"path": str(v2_path), "sha256": sha256_file(v2_path)},
        },
        "checks": {
            "candidate_membership_preserved": set(queue_by_id) == set(v1_by_id) == set(v2_by_id),
            "resolved_v1_results_preserved": not any(
                canonical(v1_by_id[candidate_id]) != canonical(v2_by_id[candidate_id])
                for candidate_id in prior_resolved
            ),
            "only_prior_unresolved_rows_retried": set(retry_ids) == prior_unresolved,
            "all_results_resolved": all(row.get("error") is None for row in v2_by_id.values()),
            "snapshot_urls_archive_only": not any("Invalid snapshot URL" in error for error in errors),
            "channel_totals": dict(channel_totals),
            "available_by_channel": dict(available_by_channel),
            "available_snapshot_count": sum(row.get("available") is True for row in v2_by_id.values()),
            "unavailable_snapshot_count": sum(row.get("available") is False for row in v2_by_id.values()),
        },
        "decision": {
            "availability_qa_passed": not errors,
            "capture_plan_construction_allowed": not errors,
            "candidate_capture_allowed": False,
            "binary_labeling_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "archived_page_download_operations": 0,
            "candidate_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify_registry(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    root = registry_path.resolve().parents[2]
    errors: list[str] = []
    checked: list[dict[str, object]] = []
    role_paths: dict[str, Path] = {}
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if registry.get("status") != EXPECTED_REGISTRY_STATUS:
        errors.append("Unexpected registry status")
    for item in (
        list(registry.get("inputs", []))
        + list(registry.get("implementation", []))
        + list(registry.get("outputs", []))
    ):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        role_paths[role] = path
        checked.append({"role": role, "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {role}")
    required = {
        "frozen_candidate_queue",
        "availability_report_v1",
        "availability_report_v2",
        "independent_availability_qa_v2",
        "availability_result_verifier_v2",
        "availability_result_verifier_tests_v2",
        "method_documentation",
    }
    missing = sorted(required - role_paths.keys())
    if missing:
        errors.append(f"Registry lacks required roles: {missing}")
    if not missing:
        result = verify(
            queue_path=role_paths["frozen_candidate_queue"],
            v1_path=role_paths["availability_report_v1"],
            v2_path=role_paths["availability_report_v2"],
        )
        errors.extend(result["errors"])
        qa = load_json(role_paths["independent_availability_qa_v2"])
        if qa.get("status") != "PASS_40_RESOLVED_29_AVAILABLE_CAPTURE_PLAN_BLOCKED":
            errors.append("Independent availability QA status changed")
    if registry.get("safety_contract") != EXPECTED_REGISTRY_SAFETY:
        errors.append("Registry safety contract changed")
    decision = registry.get("decision", {})
    if decision.get("capture_plan_construction_allowed") is not True:
        errors.append("Capture-plan construction was not released")
    if decision.get("candidate_capture_allowed") is not False:
        errors.append("Candidate capture must remain blocked")
    return {
        "analysis_id": registry.get("analysis_id"),
        "valid": not errors,
        "status": registry.get("status"),
        "checked_artifact_count": len(checked),
        "available_snapshot_count": 29,
        "unavailable_snapshot_count": 11,
        "capture_plan_construction_allowed": True,
        "candidate_capture_allowed": False,
        "errors": errors,
        "checked": checked,
    }
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--availability-v1", type=Path)
    parser.add_argument("--availability-v2", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.registry is not None:
        if any(value is not None for value in (
            args.queue, args.availability_v1, args.availability_v2, args.output
        )):
            parser.error("--registry cannot be combined with result inputs")
        result = verify_registry(args.registry)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1
    if any(value is None for value in (
        args.queue, args.availability_v1, args.availability_v2, args.output
    )):
        parser.error("provide --registry or all four result input/output arguments")
    assert args.queue and args.availability_v1 and args.availability_v2 and args.output
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    result = verify(queue_path=args.queue, v1_path=args.availability_v1, v2_path=args.availability_v2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
