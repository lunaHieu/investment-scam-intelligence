"""Crash-safe executor for the frozen SEC/IAPD V10 availability retry.

The executor reserves ``availability_report_v10.json.partial`` before the first
request, checkpoints after every candidate attempt, and never resumes or
overwrites either a partial or final output.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.execute_sec_edgar_iapd_wayback_availability_v1 import (
    RateLimitStop,
    fetch_json,
    parse_response,
)
from scripts.retry_sec_edgar_iapd_wayback_availability_v4 import (
    cooldown_state,
    read_jsonl,
    request_url,
    unresolved_ids,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


EXPECTED_RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V10"
AUTHORITATIVE_MODULE = "scripts.retry_sec_edgar_iapd_wayback_availability_v10"
FORBIDDEN_GATES = (
    "candidate_live_domain_access_allowed",
    "archived_page_download_allowed",
    "artifact_capture_allowed",
    "labeling_allowed",
    "validation_or_test_opening_allowed",
    "training_allowed",
)


def _parse_aware(value: str, field: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _same_instant(left: datetime, right: datetime) -> bool:
    return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)


def validate_release(release_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the immutable V10 authorization and its V9 parent."""

    release = load_object(release_path)
    if release.get("release_id") != EXPECTED_RELEASE_ID:
        raise ValueError("Unexpected V10 availability retry release")
    root = release_path.resolve().parents[1]
    for item in release.get("basis", []):
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"V10 basis mismatch: {item.get('role')}")
    for name, item in release.get("inputs", {}).items():
        path = Path(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"V10 input mismatch: {name}")

    inputs = release["inputs"]
    qa = load_object(Path(inputs["independent_qa_v9"]["path"]))
    if qa.get("status") != inputs["independent_qa_v9"]["required_status"]:
        raise ValueError("Availability V9 independent QA is not the required partial PASS")
    prior = load_object(Path(inputs["partial_report_v9"]["path"]))
    expected = release["prior_outcome_contract"]
    observed = {
        "requested_candidate_count": prior["requested_candidate_count"],
        "cumulative_network_request_count": prior["cumulative_network_request_count"],
        "resolved_result_count": sum(row.get("error") is None for row in prior["results"]),
        "available_snapshot_count": prior["available_snapshot_count"],
        "unavailable_snapshot_count": prior["unavailable_snapshot_count"],
        "unresolved_error_count": prior["unresolved_error_count"],
        "stopped_on_http_429": prior["stopped_on_http_429"],
    }
    if any(expected.get(key) != value for key, value in observed.items()):
        raise ValueError("Availability V9 prior outcome changed")
    if expected.get("resolved_results_must_remain_byte_equivalent") is not True:
        raise PermissionError("Resolved-row preservation authorization is missing")
    if expected.get("only_error_rows_may_be_retried") is not True:
        raise PermissionError("Unresolved-only authorization is missing")
    observed_unresolved_ids = [
        str(row["availability_plan_id"]) for row in prior["results"] if row.get("error") is not None
    ]
    if observed_unresolved_ids != expected.get("ordered_unresolved_availability_plan_ids"):
        raise ValueError("V10 ordered unresolved identity set changed")
    observed_cohorts = {
        cohort: sum(
            row.get("error") is not None and row.get("cohort") == cohort for row in prior["results"]
        )
        for cohort in ("DEVELOPMENT", "EXTERNAL_HOLDOUT")
    }
    if observed_cohorts != expected.get("unresolved_cohort_counts"):
        raise ValueError("V10 unresolved cohort composition changed")

    plan = read_jsonl(Path(inputs["availability_plan"]["path"]))
    plan_ids = [row["availability_plan_id"] for row in plan]
    prior_ids = [row["availability_plan_id"] for row in prior["results"]]
    if len(plan) != int(inputs["availability_plan"]["record_count"]):
        raise ValueError("V10 plan row count changed")
    if plan_ids != prior_ids or len(plan_ids) != len(set(plan_ids)):
        raise ValueError("V10 plan/result identity or order changed")

    cooldown = release["cooldown_contract"]
    parent_created_at = _parse_aware(str(prior["created_at"]), "parent report created_at")
    release_created_at = _parse_aware(str(release["created_at"]), "release created_at")
    declared_parent = _parse_aware(str(cooldown["prior_attempt_created_at"]), "prior_attempt_created_at")
    not_before = _parse_aware(str(cooldown["not_before"]), "not_before")
    minimum = int(cooldown.get("minimum_cooldown_seconds", 0))
    if minimum < 86400:
        raise ValueError("V10 cooldown is shorter than 24 hours")
    if not _same_instant(parent_created_at, declared_parent):
        raise ValueError("V10 cooldown is not bound to the actual V9 report created_at")
    if not _same_instant(not_before, parent_created_at + timedelta(seconds=minimum)):
        raise ValueError("V10 not_before is not exactly parent created_at plus cooldown")
    if release_created_at < parent_created_at or release_created_at >= not_before:
        raise ValueError("V10 release created_at is outside the offline preparation window")
    if cooldown.get("executor_must_fail_closed_before_not_before") is not True:
        raise PermissionError("Pre-gate fail-closed authorization is missing")

    contract = release["retry_contract"]
    retry_count = len(unresolved_ids(prior))
    if retry_count != 2 or int(contract.get("maximum_retry_candidate_count", -1)) != retry_count:
        raise ValueError("V10 retry population changed")
    if float(contract.get("minimum_delay_seconds", 0)) < 60.0:
        raise ValueError("V10 minimum pacing is below 60 seconds")
    if float(contract.get("request_rate_per_second_maximum", 1)) > (1.0 / 60.0) + 1e-9:
        raise ValueError("V10 declared request rate exceeds one request per 60 seconds")
    if int(contract.get("maximum_attempts_per_candidate", 0)) != 1:
        raise ValueError("V10 must allow exactly one attempt per unresolved candidate")
    if contract.get("endpoint") != "https://archive.org/wayback/available":
        raise ValueError("V10 endpoint changed")
    if set(contract.get("allowed_network_hosts", [])) != {"archive.org", "web.archive.org"}:
        raise ValueError("V10 network allowlist changed")
    for flag in (
        "https_only",
        "stop_on_http_429",
        "errors_are_preserved",
        "errors_are_not_interpreted_as_no_snapshot",
    ):
        if contract.get(flag) is not True:
            raise PermissionError(f"V10 required guard is not authorized: {flag}")
    if contract.get("automatic_external_redirect_following") is not False:
        raise PermissionError("V10 external redirects must remain disabled")
    if contract.get("output_overwrite_allowed") is not False:
        raise PermissionError("V10 output overwrite must remain disabled")
    if int(contract.get("maximum_redirects", -1)) != 3:
        raise ValueError("V10 maximum redirects changed")
    if int(contract.get("timeout_seconds", 0)) != 30:
        raise ValueError("V10 timeout changed")
    if int(contract.get("maximum_response_bytes", 0)) != 2097152:
        raise ValueError("V10 response-size bound changed")

    decision = release["decision"]
    if decision.get("unresolved_only_retry_allowed_after_not_before") is not True:
        raise PermissionError("V10 unresolved-only retry is not authorized")
    for gate in FORBIDDEN_GATES:
        if decision.get(gate) is not False:
            raise PermissionError(f"V10 opened forbidden gate: {gate}")
    expected_output = Path(inputs["partial_report_v9"]["path"]).parent / "availability_report_v10.json"
    if Path(release["planned_output"]["path"]) != expected_output:
        raise ValueError("V10 planned output path changed")
    if release["planned_output"].get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V10":
        raise ValueError("V10 planned report identity changed")
    return release, prior


def _dump_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _exclusive_create(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_dump_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_checkpoint(path: Path, value: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".checkpoint-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_dump_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _base_result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in (
            "availability_plan_id",
            "shortlist_id",
            "cohort",
            "candidate_host",
            "candidate_url",
            "query_timestamp",
        )
    }


def _journal(
    release_path: Path,
    release: dict[str, Any],
    prior: dict[str, Any],
    started_at: str,
    attempted: list[dict[str, Any]],
    pending_ids: list[str],
    request_count: int,
    stopped: bool,
) -> dict[str, Any]:
    return {
        "journal_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_V10_EXECUTION_JOURNAL",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": started_at,
        "release_path": str(release_path.resolve()),
        "release_sha256": sha256_file(release_path),
        "parent_report_path": release["inputs"]["partial_report_v9"]["path"],
        "parent_report_sha256": release["inputs"]["partial_report_v9"]["sha256"],
        "resolved_results_reused_from_v9": sum(row.get("error") is None for row in prior["results"]),
        "retry_candidate_count": len(unresolved_ids(prior)),
        "attempted_retry_results": deepcopy(attempted),
        "attempted_availability_plan_ids": [row["availability_plan_id"] for row in attempted],
        "pending_availability_plan_ids": list(pending_ids),
        "network_request_count_this_attempt": request_count,
        "stopped_on_http_429": stopped,
        "resume_allowed": False,
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "only_archive_availability_hosts_accessed": True,
            "archived_page_download_operations": 0,
            "artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def execute(
    release_path: Path,
    now: datetime | None = None,
    *,
    after_checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute V10 once; any existing partial or final artifact fails closed."""

    release, prior = validate_release(release_path)
    ready, remaining = cooldown_state(release, now)
    if not ready:
        raise PermissionError(f"V10 cooldown gate is closed for another {remaining:.0f} seconds")
    output_path = Path(release["planned_output"]["path"])
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    if output_path.exists() or partial.exists():
        raise FileExistsError("Refusing to run: V10 final or partial output already exists")

    unresolved = [row for row in prior["results"] if row.get("error") is not None]
    pending_ids = [str(row["availability_plan_id"]) for row in unresolved]
    started_at = (now or datetime.now(timezone.utc).astimezone()).isoformat()
    attempted: list[dict[str, Any]] = []
    request_counter = [0]
    stopped = False
    reservation = _journal(release_path, release, prior, started_at, attempted, pending_ids, 0, False)
    _exclusive_create(partial, reservation)

    contract = release["retry_contract"]
    for prior_row in unresolved:
        identifier = str(prior_row["availability_plan_id"])
        base = _base_result(prior_row)
        try:
            payload = fetch_json(
                request_url(contract["endpoint"], prior_row["candidate_url"], contract["target_timestamp"]),
                contract,
                request_counter,
            )
            result = {**base, "queried": True, **parse_response(payload), "error": None}
        except RateLimitStop as error:
            stopped = True
            result = {
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": "429",
                "error": f"{type(error).__name__}: {error}",
            }
        except Exception as error:
            result = {
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": None,
                "error": f"{type(error).__name__}: {error}",
            }
        attempted.append(result)
        pending_ids.remove(identifier)
        checkpoint = _journal(
            release_path, release, prior, started_at, attempted, pending_ids, request_counter[0], stopped
        )
        _atomic_checkpoint(partial, checkpoint)
        if after_checkpoint is not None:
            after_checkpoint(deepcopy(checkpoint))
        if stopped:
            break

    attempted_by_id = {row["availability_plan_id"]: row for row in attempted}
    final_results: list[dict[str, Any]] = []
    for prior_row in prior["results"]:
        identifier = prior_row["availability_plan_id"]
        if prior_row.get("error") is None:
            final_results.append(deepcopy(prior_row))
        elif identifier in attempted_by_id:
            final_results.append(attempted_by_id[identifier])
        else:
            final_results.append(
                {
                    **_base_result(prior_row),
                    "queried": False,
                    "available": None,
                    "snapshot_timestamp": None,
                    "snapshot_url": None,
                    "snapshot_http_status": None,
                    "error": "NOT_REQUERIED_AFTER_HTTP_429_STOP_V10",
                }
            )

    unresolved_count = sum(row.get("error") is not None for row in final_results)
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if unresolved_count == 0 else "INCOMPLETE_ERRORS_PRESERVED",
        "release_path": str(release_path.resolve()),
        "release_sha256": sha256_file(release_path),
        "executor": AUTHORITATIVE_MODULE,
        "parent_report_path": release["inputs"]["partial_report_v9"]["path"],
        "parent_report_sha256": release["inputs"]["partial_report_v9"]["sha256"],
        "plan_path": release["inputs"]["availability_plan"]["path"],
        "plan_sha256": release["inputs"]["availability_plan"]["sha256"],
        "requested_candidate_count": len(final_results),
        "resolved_results_reused_from_v9": sum(row.get("error") is None for row in prior["results"]),
        "retry_candidate_count": len(unresolved),
        "retried_availability_plan_ids": [row["availability_plan_id"] for row in attempted],
        "logical_retry_attempt_count": len(attempted),
        "network_request_count_this_attempt": request_counter[0],
        "cumulative_network_request_count": prior["cumulative_network_request_count"] + request_counter[0],
        "available_snapshot_count": sum(row.get("available") is True for row in final_results),
        "unavailable_snapshot_count": sum(row.get("available") is False for row in final_results),
        "unresolved_error_count": unresolved_count,
        "stopped_on_http_429": stopped,
        "capture_plan_construction_ready": unresolved_count == 0,
        "results": final_results,
        "safety_contract": reservation["safety_contract"],
    }
    _atomic_checkpoint(partial, report)
    os.replace(partial, output_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release, prior = validate_release(args.release)
        ready, remaining = cooldown_state(release)
        print(
            json.dumps(
                {
                    "valid": True,
                    "release_id": release["release_id"],
                    "retry_rows": len(unresolved_ids(prior)),
                    "network_execution_ready": ready,
                    "seconds_until_not_before": round(remaining),
                    "authoritative_executor": AUTHORITATIVE_MODULE,
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.release)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "report_id",
                    "status",
                    "resolved_results_reused_from_v9",
                    "retry_candidate_count",
                    "network_request_count_this_attempt",
                    "unresolved_error_count",
                    "stopped_on_http_429",
                    "capture_plan_construction_ready",
                )
            },
            indent=2,
        )
    )
    return 0 if report["capture_plan_construction_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
