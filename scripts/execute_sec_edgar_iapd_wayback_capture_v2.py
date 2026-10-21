"""Crash-safe executor for the decoupled SEC/IAPD Wayback capture amendment.

The executor reserves a partial journal before network access, checkpoints after
every row, never resumes automatically, and records a small allowlisted set of
HTTP diagnostic headers.  It consumes the already frozen V5 capture release;
it does not change the capture population or any snapshot URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import parse_time
from scripts.capture_balanced_wayback_plan_v2 import fetch_archive
from scripts.execute_sec_edgar_iapd_wayback_capture_v1 import validate_release
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


AMENDMENT_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_AMENDMENT_V1"
AUTHORITATIVE_MODULE = "scripts.execute_sec_edgar_iapd_wayback_capture_v2"
DIAGNOSTIC_HEADER_ALLOWLIST = (
    "Retry-After",
    "Date",
    "Server",
    "Content-Type",
    "X-Archive-Wayback-Runtime-Error",
)


def _dump_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _exclusive_create(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_dump_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_checkpoint(path: Path, value: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".checkpoint-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_dump_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _selected_headers(error: urllib.error.HTTPError) -> dict[str, str]:
    if error.headers is None:
        return {}
    return {
        name: str(error.headers.get(name))
        for name in DIAGNOSTIC_HEADER_ALLOWLIST
        if error.headers.get(name) is not None
    }


def _base(source: dict[str, Any]) -> dict[str, Any]:
    return {
        key: source[key]
        for key in (
            "availability_plan_id",
            "shortlist_id",
            "cohort",
            "candidate_host",
            "candidate_url",
            "snapshot_timestamp",
            "snapshot_url",
            "requested_archive_url",
            "capture_path",
        )
    }


def validate_amendment(amendment_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path, Path]:
    amendment = load_object(amendment_path)
    if amendment.get("amendment_id") != AMENDMENT_ID:
        raise ValueError("Unexpected capture execution amendment")
    if amendment.get("status") != "FROZEN_DECOUPLED_CRASH_SAFE_CAPTURE_AUTHORIZATION":
        raise PermissionError("Capture execution amendment is not authorized")
    root = amendment_path.resolve().parents[1]
    for item in amendment.get("basis", []):
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Capture amendment basis mismatch: {item.get('role')}")
    release_item = amendment["inputs"]["capture_release_v5"]
    qa_item = amendment["inputs"]["independent_release_qa_v5"]
    release_path = Path(release_item["path"])
    qa_path = Path(qa_item["path"])
    if not release_path.is_file() or sha256_file(release_path) != release_item["sha256"]:
        raise ValueError("Capture V5 release hash mismatch")
    if not qa_path.is_file() or sha256_file(qa_path) != qa_item["sha256"]:
        raise ValueError("Capture V5 independent release QA hash mismatch")
    release, plan = validate_release(release_path, qa_path)
    planned_count = int(plan.get("planned_capture_count", -1))
    if planned_count < 1:
        raise ValueError("Decoupled capture population is empty or invalid")
    if amendment["execution_binding"].get("capture_plan_rows") != planned_count:
        raise ValueError("Amendment capture count changed")
    if amendment["execution_binding"].get("authorized_executor_module") != AUTHORITATIVE_MODULE:
        raise ValueError("Amendment executor module changed")
    if amendment["execution_binding"].get("availability_v10_is_capture_prerequisite") is not False:
        raise PermissionError("Capture remains incorrectly coupled to availability V10")
    if amendment["execution_binding"].get("same_process_after_availability_429_allowed") is not False:
        raise PermissionError("Amendment permits capture in the same process after availability 429")
    decision = amendment["decision"]
    if decision.get("archive_only_capture_allowed_under_v5_not_before") is not True:
        raise PermissionError("Archive-only capture is not authorized by amendment")
    for gate in (
        "candidate_live_domain_access_allowed",
        "text_extraction_allowed_before_complete_capture_qa",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "training_allowed",
    ):
        if decision.get(gate) is not False:
            raise PermissionError(f"Capture amendment opened forbidden gate: {gate}")
    return amendment, release, plan, release_path, qa_path


def validate_amendment_qa(amendment_path: Path, amendment: dict[str, Any]) -> dict[str, Any]:
    contract = amendment["independent_qa_output"]
    qa_path = Path(contract["path"])
    if not qa_path.is_file():
        raise FileNotFoundError("Capture amendment independent QA is missing")
    qa = load_object(qa_path)
    if qa.get("verification_id") != contract["verification_id"]:
        raise ValueError("Capture amendment QA identity changed")
    if qa.get("status") != contract["required_status"] or qa.get("errors") != []:
        raise PermissionError("Capture amendment independent QA did not pass")
    if qa.get("amendment", {}).get("sha256") != sha256_file(amendment_path):
        raise ValueError("Capture amendment QA hash binding mismatch")
    if qa.get("decision", {}).get("capture_execution_allowed_under_amendment") is not True:
        raise PermissionError("Capture amendment QA did not authorize execution")
    return qa


def _journal(
    amendment_path: Path,
    release_path: Path,
    qa_path: Path,
    started_at: str,
    planned: int,
    attempted: list[dict[str, Any]],
    pending_ids: list[str],
    request_count: int,
    stopped: bool,
) -> dict[str, Any]:
    return {
        "journal_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_V1_EXECUTION_JOURNAL_V2",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": started_at,
        "executor": AUTHORITATIVE_MODULE,
        "execution_amendment": {
            "path": str(amendment_path.resolve()),
            "sha256": sha256_file(amendment_path),
        },
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "release_qa": {"path": str(qa_path.resolve()), "sha256": sha256_file(qa_path)},
        "planned_capture_count": planned,
        "attempted_results": deepcopy(attempted),
        "attempted_availability_plan_ids": [row["availability_plan_id"] for row in attempted],
        "pending_availability_plan_ids": list(pending_ids),
        "network_request_count": request_count,
        "stopped_on_http_429": stopped,
        "resume_allowed": False,
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


def execute(
    amendment_path: Path,
    now: datetime | None = None,
    *,
    after_checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    amendment, release, plan, release_path, qa_path = validate_amendment(amendment_path)
    validate_amendment_qa(amendment_path, amendment)
    current = now or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    not_before = parse_time(release["execution_contract"]["not_before"])
    if current < not_before:
        raise PermissionError(
            f"Capture not-before gate is closed for {(not_before - current).total_seconds():.0f} seconds"
        )
    output_path = Path(release["planned_output"]["path"])
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    if output_path.exists() or partial.exists():
        raise FileExistsError("Refusing to run: capture final or partial output already exists")

    sources = list(plan["results"])
    pending_ids = [str(row["availability_plan_id"]) for row in sources]
    attempted: list[dict[str, Any]] = []
    request_counter = [0]
    stopped = False
    started_at = current.isoformat()
    reservation = _journal(
        amendment_path,
        release_path,
        qa_path,
        started_at,
        len(sources),
        attempted,
        pending_ids,
        0,
        False,
    )
    _exclusive_create(partial, reservation)

    contract = release["execution_contract"]
    for source in sources:
        identifier = str(source["availability_plan_id"])
        base = _base(source)
        if stopped:
            result = {
                **base,
                "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
                "final_archive_url": None,
                "redirect_count": None,
                "http_status": None,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "diagnostic_response_headers": {},
                "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP",
            }
        else:
            try:
                payload, final_url, redirects, content_type = fetch_archive(
                    source["requested_archive_url"],
                    timeout_seconds=int(contract["timeout_seconds"]),
                    delay_seconds=float(contract["minimum_delay_seconds"]),
                    request_counter=request_counter,
                    max_redirects=int(contract["maximum_redirects"]),
                )
                target = Path(source["capture_path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                raw_partial = target.with_suffix(target.suffix + ".partial")
                if target.exists() or raw_partial.exists():
                    raise FileExistsError(f"Refusing to reuse raw capture target: {target}")
                with raw_partial.open("xb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(raw_partial, target)
                result = {
                    **base,
                    "outcome": "CAPTURED",
                    "final_archive_url": final_url,
                    "redirect_count": redirects,
                    "http_status": 200,
                    "content_type": content_type,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "diagnostic_response_headers": {},
                    "error": None,
                }
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    stopped = True
                result = {
                    **base,
                    "outcome": "FAILED",
                    "final_archive_url": None,
                    "redirect_count": None,
                    "http_status": error.code,
                    "content_type": None,
                    "bytes": None,
                    "sha256": None,
                    "diagnostic_response_headers": _selected_headers(error),
                    "error": f"HTTPError: {error}",
                }
            except Exception as error:
                result = {
                    **base,
                    "outcome": "FAILED",
                    "final_archive_url": None,
                    "redirect_count": None,
                    "http_status": None,
                    "content_type": None,
                    "bytes": None,
                    "sha256": None,
                    "diagnostic_response_headers": {},
                    "error": f"{type(error).__name__}: {error}",
                }
        attempted.append(result)
        pending_ids.remove(identifier)
        checkpoint = _journal(
            amendment_path,
            release_path,
            qa_path,
            started_at,
            len(sources),
            attempted,
            pending_ids,
            request_counter[0],
            stopped,
        )
        _atomic_checkpoint(partial, checkpoint)
        if after_checkpoint is not None:
            after_checkpoint(deepcopy(checkpoint))

    captured = sum(row["outcome"] == "CAPTURED" for row in attempted)
    failed = sum(row["outcome"] == "FAILED" for row in attempted)
    not_attempted = sum(row["outcome"] == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP" for row in attempted)
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if captured == len(attempted) else "INCOMPLETE_FAILURES_PRESERVED",
        "executor": AUTHORITATIVE_MODULE,
        "execution_amendment": {
            "path": str(amendment_path.resolve()),
            "sha256": sha256_file(amendment_path),
        },
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "release_qa": {"path": str(qa_path.resolve()), "sha256": sha256_file(qa_path)},
        "plan": release["inputs"]["capture_plan"],
        "planned_capture_count": len(attempted),
        "network_request_count": request_counter[0],
        "captured_count": captured,
        "captured_by_cohort": dict(
            Counter(row["cohort"] for row in attempted if row["outcome"] == "CAPTURED")
        ),
        "failed_count": failed,
        "not_attempted_count": not_attempted,
        "stopped_on_http_429": stopped,
        "results": attempted,
        "safety_contract": reservation["safety_contract"],
    }
    _atomic_checkpoint(partial, report)
    os.replace(partial, output_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        amendment, release, plan, _, _ = validate_amendment(args.amendment)
        validate_amendment_qa(args.amendment, amendment)
        remaining = max(
            0.0,
            (
                parse_time(release["execution_contract"]["not_before"])
                - datetime.now(timezone.utc).astimezone()
            ).total_seconds(),
        )
        print(
            json.dumps(
                {
                    "valid": True,
                    "amendment_id": amendment["amendment_id"],
                    "planned_capture_count": plan["planned_capture_count"],
                    "seconds_until_not_before": round(remaining),
                    "availability_v10_is_capture_prerequisite": False,
                    "authoritative_executor": AUTHORITATIVE_MODULE,
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.amendment)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "report_id",
                    "status",
                    "planned_capture_count",
                    "network_request_count",
                    "captured_count",
                    "captured_by_cohort",
                    "failed_count",
                    "not_attempted_count",
                    "stopped_on_http_429",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
