"""Crash-safe executor for the frozen SEC/IAPD one-row capture retry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import parse_time
from scripts.capture_balanced_wayback_plan_v2 import NoRedirect, assert_archive_url
from scripts.verify_sec_edgar_iapd_wayback_capture_retry_release_v1 import verify as verify_release
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_MISSING_ROW_RETRY_RELEASE_V1"
QA_STATUS = "PASS_EXACT_MISSING_ROWS_ARCHIVE_ONLY_RETRY_RELEASE"
EXECUTOR = "scripts.execute_sec_edgar_iapd_wayback_capture_retry_v1"
HEADER_ALLOWLIST = ("Retry-After", "Date", "Server", "Content-Type", "X-Archive-Wayback-Runtime-Error")


class ResponseValidationError(ValueError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def _headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    return {name: str(headers.get(name)) for name in HEADER_ALLOWLIST if headers.get(name) is not None}


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def _checkpoint(path: Path, value: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".checkpoint-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_inputs(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    release = load_object(release_path)
    qa = load_object(release_qa_path)
    if release.get("release_id") != RELEASE_ID or release.get("status") != "FROZEN_EXACT_MISSING_ROWS_ARCHIVE_ONLY_RETRY_NOT_BEFORE_GATE":
        raise ValueError("Unexpected retry release")
    reproduced = verify_release(release_path)
    if reproduced.get("status") != QA_STATUS or reproduced.get("errors") != []:
        raise PermissionError("Retry release independent recomputation failed")
    if qa.get("status") != QA_STATUS or qa.get("errors") != []:
        raise PermissionError("Retry release QA did not pass")
    if qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise ValueError("Retry release QA binding mismatch")
    if qa.get("decision", {}).get("execution_allowed_at_or_after_not_before") is not True:
        raise PermissionError("Retry release QA did not authorize gated execution")
    if len(release.get("retry_rows", [])) != 1 or release.get("retry_capture_count") != 1:
        raise ValueError("Retry release is not the frozen one-row population")
    for completed in release.get("completed_capture_ledger", []):
        path = Path(completed["capture_path"])
        if not path.is_file() or path.stat().st_size != completed["bytes"] or sha256_file(path) != completed["sha256"]:
            raise ValueError(f"Completed capture changed: {completed.get('availability_plan_id')}")
    return release, qa


def fetch_retry(url: str, contract: dict[str, Any], request_counter: list[int]) -> tuple[bytes, dict[str, Any]]:
    opener = urllib.request.build_opener(NoRedirect())
    current = url
    redirects = 0
    while True:
        assert_archive_url(current)
        time.sleep(float(contract["minimum_delay_seconds"]))
        request = urllib.request.Request(current, headers={"User-Agent": "ISI-Research/1.0 (academic benchmark acquisition)"}, method="GET")
        request_counter[0] += 1
        try:
            response = opener.open(request, timeout=int(contract["timeout_seconds"]))
        except urllib.error.HTTPError as error:
            if error.code in {301, 302, 303, 307, 308}:
                if redirects >= int(contract["maximum_redirects"]):
                    raise ResponseValidationError("Maximum archive redirect count exceeded", {"http_status": error.code, "response_headers": _headers(error.headers)}) from error
                location = error.headers.get("Location")
                if not location:
                    raise ResponseValidationError(f"HTTP {error.code} without redirect location", {"http_status": error.code, "response_headers": _headers(error.headers)}) from error
                current = urllib.parse.urljoin(current, location)
                assert_archive_url(current)
                redirects += 1
                continue
            raise
        with response:
            status = int(response.status)
            content_type = str(response.headers.get("Content-Type") or "")
            payload = response.read(int(contract["maximum_response_bytes"]) + 1)
            response_headers = _headers(response.headers)
        diagnostics = {"final_archive_url": current, "redirect_count": redirects, "http_status": status, "content_type": content_type, "response_bytes": len(payload), "response_sha256": hashlib.sha256(payload).hexdigest(), "response_headers": response_headers}
        if status != 200:
            raise ResponseValidationError(f"Unexpected HTTP status: {status}", diagnostics)
        if not content_type.casefold().startswith(str(contract["required_content_type_prefix"]).casefold()):
            raise ResponseValidationError(f"Unexpected content type: {content_type}", diagnostics)
        if len(payload) > int(contract["maximum_response_bytes"]):
            raise ResponseValidationError("Archived HTML capture exceeds the size limit", diagnostics)
        if len(payload) < 1024:
            raise ResponseValidationError(f"Archived HTML capture is unexpectedly small: {len(payload)} bytes", diagnostics)
        return payload, diagnostics


def capture_row(row: dict[str, Any], contract: dict[str, Any], fetcher: Callable[..., tuple[bytes, dict[str, Any]]] = fetch_retry) -> tuple[dict[str, Any], int]:
    counter = [0]
    base = {key: row[key] for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url", "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path")}
    target = Path(row["capture_path"])
    raw_partial = target.with_suffix(target.suffix + ".partial")
    if target.exists() or raw_partial.exists():
        raise FileExistsError(f"Refusing to reuse raw capture target: {target}")
    try:
        payload, diagnostics = fetcher(row["requested_archive_url"], contract, counter)
        target.parent.mkdir(parents=True, exist_ok=True)
        with raw_partial.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw_partial, target)
        return {**base, "outcome": "CAPTURED", **diagnostics, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "error": None}, counter[0]
    except urllib.error.HTTPError as error:
        return {**base, "outcome": "FAILED", "final_archive_url": None, "redirect_count": None, "http_status": error.code, "content_type": None, "bytes": None, "sha256": None, "response_diagnostics": {"response_headers": _headers(error.headers)}, "error": f"HTTPError: {error}"}, counter[0]
    except ResponseValidationError as error:
        return {**base, "outcome": "FAILED", "final_archive_url": error.diagnostics.get("final_archive_url"), "redirect_count": error.diagnostics.get("redirect_count"), "http_status": error.diagnostics.get("http_status"), "content_type": error.diagnostics.get("content_type"), "bytes": None, "sha256": None, "response_diagnostics": error.diagnostics, "error": f"{type(error).__name__}: {error}"}, counter[0]
    except Exception as error:
        return {**base, "outcome": "FAILED", "final_archive_url": None, "redirect_count": None, "http_status": None, "content_type": None, "bytes": None, "sha256": None, "response_diagnostics": {}, "error": f"{type(error).__name__}: {error}"}, counter[0]


def execute(release_path: Path, release_qa_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release, _ = validate_inputs(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None or current < parse_time(release["execution_contract"]["not_before"]):
        raise PermissionError("Capture retry not-before gate is closed")
    output = Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("Refusing to run: retry final or partial output already exists")
    reservation = {"journal_id": "ISI_SEC_EDGAR_IAPD_CAPTURE_RETRY_JOURNAL_V1", "status": "PARTIAL_DO_NOT_AUTO_RESUME", "started_at": current.isoformat(), "executor": EXECUTOR, "release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "pending_availability_plan_ids": [release["retry_rows"][0]["availability_plan_id"]], "attempted_results": [], "network_request_count": 0, "resume_allowed": False}
    _write_exclusive(partial, reservation)
    result, request_count = capture_row(release["retry_rows"][0], release["execution_contract"])
    report = {"report_id": release["planned_output"]["report_id"], "created_at": datetime.now(timezone.utc).astimezone().isoformat(), "status": "COMPLETE" if result["outcome"] == "CAPTURED" else "INCOMPLETE_FAILURE_PRESERVED", "executor": EXECUTOR, "release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "planned_capture_count": 1, "network_request_count": request_count, "captured_count": int(result["outcome"] == "CAPTURED"), "failed_count": int(result["outcome"] == "FAILED"), "stopped_on_http_429": result.get("http_status") == 429, "results": [result], "safety_contract": {"candidate_live_domain_access_operations": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}}
    _checkpoint(partial, report)
    os.replace(partial, output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release, _ = validate_inputs(args.release, args.release_qa)
    if args.verify_only:
        remaining = max(0, round((parse_time(release["execution_contract"]["not_before"]) - datetime.now(timezone.utc).astimezone()).total_seconds()))
        print(json.dumps({"valid": True, "release_id": release["release_id"], "retry_capture_count": 1, "seconds_until_not_before": remaining, "authoritative_executor": EXECUTOR}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "network_request_count", "captured_count", "failed_count", "stopped_on_http_429")}, indent=2))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
