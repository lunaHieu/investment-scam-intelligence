"""Retry unresolved frozen Wayback captures after a verified cooldown."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_balanced_wayback_plan_v2 import fetch_archive
from scripts.capture_target_text_corpus_v1_wayback_plan import EXPECTED_BY_CHANNEL, validate_plan
from scripts.query_target_text_corpus_v1_wayback_availability import load_json, resolve, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_RETRY_V2"
EXPECTED_STATUS = "FROZEN_COOLDOWN_RETRY_AUTHORIZED_CAPTURE_UNEXECUTED"
PRIOR_REPORT_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_REPORT_V1"


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed


def unresolved_candidate_ids(prior: dict[str, Any]) -> list[str]:
    return [
        str(row["candidate_id"])
        for row in prior.get("results", [])
        if row.get("outcome") != "CAPTURED"
    ]


def validate_protocol(protocol_path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    errors: list[str] = []
    role_paths: dict[str, Path] = {}
    if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        errors.append("Unexpected capture retry protocol ID")
    if protocol.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected capture retry protocol status")
    for item in protocol.get("basis", []):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        role_paths[role] = path
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            errors.append(f"Basis artifact missing or changed: {role}")
    plan_path = role_paths.get("frozen_capture_plan_v1")
    prior_path = role_paths.get("failed_capture_report_v1")
    plan: dict[str, Any] = {}
    prior: dict[str, Any] = {}
    if plan_path is None or prior_path is None:
        errors.append("Retry basis lacks plan or prior report")
    else:
        try:
            plan = validate_plan(plan_path, sha256_file(plan_path))
            prior = load_json(prior_path)
        except (FileNotFoundError, KeyError, ValueError) as error:
            errors.append(str(error))
    expected = protocol.get("prior_outcome_contract", {})
    observed = {
        "planned_capture_count": prior.get("planned_capture_count"),
        "network_request_count": prior.get("network_request_count"),
        "captured_count": prior.get("captured_count"),
        "failed_count": prior.get("failed_count"),
        "not_attempted_count": prior.get("not_attempted_count"),
        "stopped_on_http_429": prior.get("stopped_on_http_429"),
    }
    for key, value in observed.items():
        if expected.get(key) != value:
            errors.append(f"Prior capture outcome changed: {key}")
    if prior.get("report_id") != PRIOR_REPORT_ID:
        errors.append("Unexpected prior capture report ID")
    plan_by_id = {str(row["candidate_id"]): row for row in plan.get("results", [])}
    prior_by_id = {str(row["candidate_id"]): row for row in prior.get("results", [])}
    if len(plan_by_id) != 29 or set(plan_by_id) != set(prior_by_id):
        errors.append("Plan/prior candidate membership changed")
    # The gate is a historical snapshot. Current file existence can legitimately
    # change after a later successful execution and must not invalidate it.
    retry = protocol.get("retry_contract", {})
    if float(retry.get("minimum_delay_seconds", 0)) < 10.0:
        errors.append("Retry delay is below ten seconds")
    if retry.get("maximum_attempts_per_candidate") != 1:
        errors.append("Retry attempt count changed")
    for key, value in {
        "allowed_network_host": "web.archive.org",
        "raw_replay_modifier_required": True,
        "https_only": True,
        "automatic_external_redirect_following": False,
        "stop_on_http_429": True,
        "errors_are_preserved": True,
        "live_candidate_domain_access_allowed": False,
        "raw_capture_overwrite_allowed": False,
        "report_overwrite_allowed": False,
    }.items():
        if retry.get(key) != value:
            errors.append(f"Retry safety guard changed: {key}")
    cooldown_ready = False
    if prior.get("created_at"):
        reference_now = now or datetime.now(timezone.utc).astimezone()
        elapsed_hours = (reference_now - parse_time(str(prior["created_at"]))).total_seconds() / 3600
        cooldown_ready = elapsed_hours >= float(retry.get("minimum_cooldown_hours_after_v1", 24))
        if not cooldown_ready:
            errors.append("Required capture retry cooldown has not elapsed")
    return {
        "valid": not errors,
        "protocol": protocol,
        "plan": plan,
        "plan_path": plan_path,
        "prior": prior,
        "prior_path": prior_path,
        "retry_candidate_count": len(unresolved_candidate_ids(prior)),
        "cooldown_ready": cooldown_ready,
        "errors": errors,
    }


def execute(protocol_path: Path) -> dict[str, Any]:
    validation = validate_protocol(protocol_path)
    if not validation["valid"]:
        raise ValueError(f"Capture retry protocol validation failed: {validation['errors']}")
    protocol = validation["protocol"]
    plan = validation["plan"]
    prior = validation["prior"]
    plan_path = validation["plan_path"]
    prior_path = validation["prior_path"]
    assert isinstance(plan_path, Path) and isinstance(prior_path, Path)
    retry = protocol["retry_contract"]
    output_path = Path(protocol["planned_output"]["path"])
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output_path}")
    prior_by_id = {str(row["candidate_id"]): row for row in prior["results"]}
    # File-state checks belong immediately before execution, not in the
    # historical protocol verifier. This preflight occurs before any request.
    for row in plan["results"]:
        candidate_id = str(row["candidate_id"])
        prior_row = prior_by_id[candidate_id]
        target = Path(str(row["capture_path"]))
        if prior_row.get("outcome") == "CAPTURED":
            if not target.is_file() or sha256_file(target) != prior_row.get("sha256"):
                raise ValueError(f"Prior captured bytes missing or changed: {candidate_id}")
        elif target.exists():
            raise FileExistsError(f"Unresolved capture target already exists: {target}")
    request_counter = [0]
    results: list[dict[str, Any]] = []
    retried_ids: list[str] = []
    stopped_on_429 = False
    for row in plan["results"]:
        candidate_id = str(row["candidate_id"])
        prior_row = prior_by_id[candidate_id]
        if prior_row.get("outcome") == "CAPTURED":
            target = Path(str(row["capture_path"]))
            if sha256_file(target) != prior_row.get("sha256"):
                raise ValueError(f"Prior captured bytes changed: {candidate_id}")
            results.append(dict(prior_row))
            continue
        base = dict(row)
        if stopped_on_429:
            results.append({
                **base,
                "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP_V2",
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": None,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP_V2",
            })
            continue
        retried_ids.append(candidate_id)
        try:
            payload, final_url, redirects, content_type = fetch_archive(
                str(row["requested_archive_url"]),
                timeout_seconds=int(retry["timeout_seconds"]),
                delay_seconds=float(retry["minimum_delay_seconds"]),
                request_counter=request_counter,
            )
            target = Path(str(row["capture_path"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            results.append({
                **base,
                "outcome": "CAPTURED",
                "final_archive_url": final_url,
                "redirect_count": redirects,
                "http_status": 200,
                "content_type": content_type,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "error": None,
            })
        except urllib.error.HTTPError as error:
            if error.code == 429:
                stopped_on_429 = True
            results.append({
                **base,
                "outcome": "FAILED",
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": error.code,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "error": f"HTTPError: {error}",
            })
        except Exception as error:
            results.append({
                **base,
                "outcome": "FAILED",
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": None,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "error": f"{type(error).__name__}: {error}",
            })
    captured_by_channel = Counter(
        str(row["channel_id"]) for row in results if row["outcome"] == "CAPTURED"
    )
    captured_count = sum(row["outcome"] == "CAPTURED" for row in results)
    report = {
        "report_id": protocol["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if captured_count == 29 else "INCOMPLETE_FAILURES_PRESERVED",
        "protocol_path": str(protocol_path.resolve()),
        "protocol_sha256": sha256_file(protocol_path),
        "plan_path": str(plan_path.resolve()),
        "plan_sha256": sha256_file(plan_path),
        "parent_report_path": str(prior_path.resolve()),
        "parent_report_sha256": sha256_file(prior_path),
        "planned_capture_count": 29,
        "prior_captured_results_reused": sum(
            row.get("outcome") == "CAPTURED" for row in prior["results"]
        ),
        "retry_candidate_count": len(unresolved_candidate_ids(prior)),
        "retried_candidate_ids": retried_ids,
        "network_request_count_this_attempt": request_counter[0],
        "cumulative_capture_network_request_count": int(prior["network_request_count"])
        + request_counter[0],
        "captured_count": captured_count,
        "captured_by_channel": dict(captured_by_channel),
        "failed_count": sum(row["outcome"] == "FAILED" for row in results),
        "not_attempted_count": sum(
            row["outcome"] == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP_V2" for row in results
        ),
        "stopped_on_http_429": stopped_on_429,
        "results": results,
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "only_web_archive_host_accessed": True,
            "raw_replay_modifier_used": True,
            "automatic_external_redirect_following": False,
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
        print(json.dumps({
            "valid": result["valid"],
            "retry_candidate_count": result["retry_candidate_count"],
            "cooldown_ready": result["cooldown_ready"],
            "errors": result["errors"],
        }, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1
    report = execute(args.protocol)
    print(json.dumps({key: report[key] for key in (
        "report_id", "status", "retry_candidate_count", "network_request_count_this_attempt",
        "cumulative_capture_network_request_count", "captured_count", "captured_by_channel",
        "failed_count", "not_attempted_count", "stopped_on_http_429"
    )}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
