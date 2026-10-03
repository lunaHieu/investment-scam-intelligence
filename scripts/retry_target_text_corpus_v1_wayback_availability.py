"""Retry only unresolved Target Text Corpus V1 Wayback availability rows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.query_target_text_corpus_v1_wayback_availability import (
    ALLOWED_ARCHIVE_HOSTS,
    RateLimitStop,
    availability_url,
    fetch_json,
    load_json,
    parse_availability_response,
    resolve,
    sha256_file,
)


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_RETRY_V2"
EXPECTED_STATUS = "FROZEN_UNRESOLVED_ONLY_COOLDOWN_RETRY_AUTHORIZED_CAPTURE_BLOCKED"
PRIOR_REPORT_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_REPORT_V1"


def retry_candidate_ids(prior: dict[str, Any]) -> list[str]:
    return [str(row["candidate_id"]) for row in prior.get("results", []) if row.get("error")]


def validate_protocol(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    errors: list[str] = []
    role_paths: dict[str, Path] = {}
    if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        errors.append("Unexpected retry protocol ID")
    if protocol.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected retry protocol status")
    for item in protocol.get("basis", []):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        role_paths[role] = path
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            errors.append(f"Basis artifact missing or changed: {role}")
    prior_path = role_paths.get("partial_availability_report_v1")
    prior: dict[str, Any] = {}
    if prior_path is None or not prior_path.is_file():
        errors.append("Partial availability report V1 is missing")
    else:
        prior = load_json(prior_path)
        expected = protocol.get("prior_outcome_contract", {})
        observed = {
            "requested_candidate_count": prior.get("requested_candidate_count"),
            "network_request_count": prior.get("network_request_count"),
            "resolved_result_count": sum(
                row.get("error") is None for row in prior.get("results", [])
            ),
            "available_snapshot_count": prior.get("available_snapshot_count"),
            "unavailable_snapshot_count": prior.get("unavailable_snapshot_count"),
            "unresolved_error_count": prior.get("unresolved_error_count"),
            "stopped_on_http_429": prior.get("stopped_on_http_429"),
        }
        for key, value in observed.items():
            if expected.get(key) != value:
                errors.append(f"Prior availability outcome changed: {key}")
        if prior.get("report_id") != PRIOR_REPORT_ID:
            errors.append("Unexpected prior availability report ID")
        if len(prior.get("results", [])) != 40:
            errors.append("Prior availability report must retain 40 rows")
        ids = [str(row.get("candidate_id")) for row in prior.get("results", [])]
        if len(ids) != len(set(ids)):
            errors.append("Prior availability report contains duplicate candidate IDs")
        if len(retry_candidate_ids(prior)) != 31:
            errors.append("Retry candidate count changed")
    retry = protocol.get("retry_contract", {})
    if retry.get("endpoint") != "https://archive.org/wayback/available":
        errors.append("Retry endpoint changed")
    if set(retry.get("allowed_network_hosts", [])) != ALLOWED_ARCHIVE_HOSTS:
        errors.append("Retry allowed-host set changed")
    if float(retry.get("minimum_delay_seconds", 0)) < 6.0:
        errors.append("Retry delay is below the frozen cooldown pacing")
    if retry.get("maximum_attempts_per_candidate") != 1:
        errors.append("Retry attempt count changed")
    if retry.get("maximum_retry_candidate_count") != 31:
        errors.append("Retry candidate cap changed")
    for key, expected in {
        "https_only": True,
        "automatic_external_redirect_following": False,
        "stop_on_http_429": True,
        "errors_are_not_interpreted_as_no_snapshot": True,
        "archived_page_download_allowed": False,
        "live_candidate_domain_access_allowed": False,
        "output_overwrite_allowed": False,
    }.items():
        if retry.get(key) != expected:
            errors.append(f"Retry safety guard changed: {key}")
    return {
        "valid": not errors,
        "protocol": protocol,
        "prior_path": prior_path,
        "prior": prior,
        "retry_candidate_count": len(retry_candidate_ids(prior)),
        "errors": errors,
    }


def execute(protocol_path: Path) -> dict[str, Any]:
    validation = validate_protocol(protocol_path)
    if not validation["valid"]:
        raise ValueError(f"Retry protocol validation failed: {validation['errors']}")
    protocol = validation["protocol"]
    prior = validation["prior"]
    prior_path = validation["prior_path"]
    assert isinstance(prior_path, Path)
    retry = protocol["retry_contract"]
    output_path = Path(protocol["planned_output"]["path"])
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output_path}")
    request_counter = [0]
    results: list[dict[str, Any]] = []
    stopped_on_429 = False
    retried_ids: list[str] = []
    for prior_row in prior["results"]:
        if prior_row.get("error") is None:
            results.append(dict(prior_row))
            continue
        base = {
            key: prior_row[key]
            for key in (
                "candidate_id", "channel_id", "channel_target_stratum",
                "candidate_host", "candidate_url", "query_timestamp"
            )
        }
        if stopped_on_429:
            results.append({
                **base,
                "queried": False,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": None,
                "error": "NOT_REQUERIED_AFTER_HTTP_429_STOP_V2",
            })
            continue
        retried_ids.append(str(prior_row["candidate_id"]))
        url = availability_url(retry["endpoint"], prior_row["candidate_url"], retry["target_timestamp"])
        try:
            payload = fetch_json(
                url,
                timeout_seconds=int(retry["timeout_seconds"]),
                delay_seconds=float(retry["minimum_delay_seconds"]),
                request_counter=request_counter,
            )
            parsed = parse_availability_response(payload)
            results.append({**base, "queried": True, **parsed, "error": None})
        except RateLimitStop as error:
            stopped_on_429 = True
            results.append({
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": "429",
                "error": f"{type(error).__name__}: {error}",
            })
        except Exception as error:  # preserve retry uncertainty exactly
            results.append({
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": None,
                "error": f"{type(error).__name__}: {error}",
            })
    unresolved = sum(row["error"] is not None for row in results)
    report = {
        "report_id": protocol["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED",
        "protocol_path": str(protocol_path.resolve()),
        "protocol_sha256": sha256_file(protocol_path),
        "parent_report_path": str(prior_path.resolve()),
        "parent_report_sha256": sha256_file(prior_path),
        "queue_path": prior["queue_path"],
        "queue_sha256": prior["queue_sha256"],
        "requested_candidate_count": len(results),
        "resolved_results_reused_from_v1": sum(
            row.get("error") is None for row in prior["results"]
        ),
        "retry_candidate_count": len(retry_candidate_ids(prior)),
        "retried_candidate_ids": retried_ids,
        "network_request_count_this_attempt": request_counter[0],
        "cumulative_network_request_count": int(prior["network_request_count"])
        + request_counter[0],
        "available_snapshot_count": sum(row["available"] is True for row in results),
        "unavailable_snapshot_count": sum(row["available"] is False for row in results),
        "unresolved_error_count": unresolved,
        "stopped_on_http_429": stopped_on_429,
        "capture_planning_ready": unresolved == 0,
        "results": results,
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "only_archive_availability_hosts_accessed": True,
            "archived_page_download_operations": 0,
            "candidate_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = validate_protocol(args.protocol)
        public = {
            "valid": result["valid"],
            "retry_candidate_count": result["retry_candidate_count"],
            "errors": result["errors"],
        }
        print(json.dumps(public, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1
    report = execute(args.protocol)
    print(json.dumps({key: report[key] for key in (
        "report_id", "status", "resolved_results_reused_from_v1",
        "retry_candidate_count", "network_request_count_this_attempt",
        "cumulative_network_request_count", "available_snapshot_count",
        "unavailable_snapshot_count", "unresolved_error_count",
        "stopped_on_http_429", "capture_planning_ready"
    )}, ensure_ascii=False, indent=2))
    return 0 if report["capture_planning_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
