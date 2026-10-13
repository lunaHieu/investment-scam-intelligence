"""Retry unresolved SEC/IAPD Wayback availability rows after a pinned cooldown."""

from __future__ import annotations

import argparse
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.execute_sec_edgar_iapd_wayback_availability_v1 import RateLimitStop, fetch_json, parse_response
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def unresolved_ids(report: dict[str, Any]) -> list[str]:
    return [str(row["availability_plan_id"]) for row in report["results"] if row.get("error") is not None]


def request_url(endpoint: str, candidate_url: str, timestamp: str) -> str:
    return endpoint + "?" + urllib.parse.urlencode({"url": candidate_url, "timestamp": timestamp})


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Cooldown timestamp must include a timezone")
    return parsed


def cooldown_state(release: dict[str, Any], now: datetime | None = None) -> tuple[bool, float]:
    current = now or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    not_before = parse_time(release["cooldown_contract"]["not_before"])
    remaining = max(0.0, (not_before - current).total_seconds())
    return remaining == 0.0, remaining


def validate_release(release_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    release = load_object(release_path)
    if release.get("release_id") != "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V3":
        raise ValueError("Unexpected availability retry release")
    root = release_path.resolve().parents[1]
    for item in release["basis"]:
        if sha256_file(root / item["path"]) != item["sha256"]:
            raise ValueError("Availability retry basis mismatch")
    for item in release["inputs"].values():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("Availability retry input mismatch")
    qa = load_object(Path(release["inputs"]["independent_qa_v2"]["path"]))
    if qa.get("status") != release["inputs"]["independent_qa_v2"]["required_status"]:
        raise ValueError("Availability V2 independent QA is not PASS")
    prior = load_object(Path(release["inputs"]["partial_report_v2"]["path"]))
    expected = release["prior_outcome_contract"]
    observed = {
        "requested_candidate_count": prior["requested_candidate_count"],
        "cumulative_network_request_count": prior["cumulative_network_request_count"],
        "resolved_result_count": sum(row["error"] is None for row in prior["results"]),
        "available_snapshot_count": prior["available_snapshot_count"],
        "unavailable_snapshot_count": prior["unavailable_snapshot_count"],
        "unresolved_error_count": prior["unresolved_error_count"],
        "stopped_on_http_429": prior["stopped_on_http_429"],
    }
    if any(expected[key] != value for key, value in observed.items()):
        raise ValueError("Availability V2 prior outcome changed")
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    if len(plan) != len(prior["results"]) or [row["availability_plan_id"] for row in plan] != [row["availability_plan_id"] for row in prior["results"]]:
        raise ValueError("Availability retry plan/result membership changed")
    cooldown = release["cooldown_contract"]
    prior_at = parse_time(cooldown["prior_attempt_created_at"])
    not_before = parse_time(cooldown["not_before"])
    if (not_before - prior_at).total_seconds() < cooldown["minimum_cooldown_seconds"] or cooldown["minimum_cooldown_seconds"] < 86400:
        raise ValueError("Availability retry cooldown is shorter than 24 hours")
    contract = release["retry_contract"]
    if len(unresolved_ids(prior)) != contract["maximum_retry_candidate_count"] or float(contract["minimum_delay_seconds"]) < 30.0 or contract["maximum_attempts_per_candidate"] != 1:
        raise ValueError("Availability retry population or pacing changed")
    if set(contract["allowed_network_hosts"]) != {"archive.org", "web.archive.org"} or contract["endpoint"] != "https://archive.org/wayback/available":
        raise ValueError("Availability retry endpoint/allowlist changed")
    if release["decision"].get("unresolved_only_retry_allowed_after_not_before") is not True:
        raise PermissionError("Availability retry is closed")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if release["decision"].get(gate) is not False:
            raise PermissionError(f"Availability retry opened forbidden gate: {gate}")
    return release, prior


def execute(release_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release, prior = validate_release(release_path)
    ready, seconds_remaining = cooldown_state(release, now)
    if not ready:
        raise PermissionError(f"Cooldown gate is closed for another {seconds_remaining:.0f} seconds")
    output_path = Path(release["planned_output"]["path"])
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    if output_path.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite availability retry result")
    contract = release["retry_contract"]
    request_counter = [0]
    results: list[dict[str, Any]] = []
    retried: list[str] = []
    stopped = False
    attempt_index = 0
    for prior_row in prior["results"]:
        if prior_row.get("error") is None:
            results.append(dict(prior_row))
            continue
        base = {key: prior_row[key] for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url", "query_timestamp")}
        if stopped:
            results.append({**base, "queried": False, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None, "error": "NOT_REQUERIED_AFTER_HTTP_429_STOP_V3"})
            continue
        attempt_index += 1
        retried.append(prior_row["availability_plan_id"])
        try:
            payload = fetch_json(request_url(contract["endpoint"], prior_row["candidate_url"], contract["target_timestamp"]), contract, request_counter)
            results.append({**base, "queried": True, **parse_response(payload), "error": None})
        except RateLimitStop as error:
            stopped = True
            results.append({**base, "queried": True, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": "429", "error": f"{type(error).__name__}: {error}"})
        except Exception as error:
            results.append({**base, "queried": True, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None, "error": f"{type(error).__name__}: {error}"})
        if attempt_index % 10 == 0 or attempt_index == contract["maximum_retry_candidate_count"]:
            print(json.dumps({"retry_progress": attempt_index, "retry_total": contract["maximum_retry_candidate_count"], "network_requests": request_counter[0], "stopped_on_429": stopped}), flush=True)
    unresolved = sum(row["error"] is not None for row in results)
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED",
        "release_path": str(release_path.resolve()),
        "release_sha256": sha256_file(release_path),
        "parent_report_path": release["inputs"]["partial_report_v2"]["path"],
        "parent_report_sha256": release["inputs"]["partial_report_v2"]["sha256"],
        "plan_path": release["inputs"]["availability_plan"]["path"],
        "plan_sha256": release["inputs"]["availability_plan"]["sha256"],
        "requested_candidate_count": len(results),
        "resolved_results_reused_from_v2": sum(row["error"] is None for row in prior["results"]),
        "retry_candidate_count": len(unresolved_ids(prior)),
        "retried_availability_plan_ids": retried,
        "network_request_count_this_attempt": request_counter[0],
        "cumulative_network_request_count": prior["cumulative_network_request_count"] + request_counter[0],
        "available_snapshot_count": sum(row["available"] is True for row in results),
        "unavailable_snapshot_count": sum(row["available"] is False for row in results),
        "unresolved_error_count": unresolved,
        "stopped_on_http_429": stopped,
        "capture_plan_construction_ready": unresolved == 0,
        "results": results,
        "safety_contract": {"candidate_live_domain_access_operations": 0, "only_archive_availability_hosts_accessed": True, "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(output_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release, prior = validate_release(args.release)
        ready, seconds_remaining = cooldown_state(release)
        print(json.dumps({"valid": True, "release_id": release["release_id"], "retry_rows": len(unresolved_ids(prior)), "network_execution_ready": ready, "seconds_until_not_before": round(seconds_remaining)}, indent=2))
        return 0
    report = execute(args.release)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "resolved_results_reused_from_v2", "retry_candidate_count", "network_request_count_this_attempt", "cumulative_network_request_count", "available_snapshot_count", "unavailable_snapshot_count", "unresolved_error_count", "stopped_on_http_429", "capture_plan_construction_ready")}, ensure_ascii=False, indent=2))
    return 0 if report["capture_plan_construction_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
