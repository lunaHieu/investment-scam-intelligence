"""Crash-safe B4 executor for the exact 70-row ready-channel availability plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1 import (
    PASS_STATUS,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXECUTOR = "scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1"
USER_AGENT = "ISI-Research/2.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
PRESERVED_HEADERS = ("Retry-After", "Date", "Server", "Content-Type", "X-Archive-Wayback-Runtime-Error")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class AvailabilityResponseError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class AvailabilityRateLimitStop(AvailabilityResponseError):
    """HTTP 429 stops this release immediately."""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _headers(headers: Any) -> dict[str, str]:
    return {name: str(headers.get(name)) for name in PRESERVED_HEADERS if headers is not None and headers.get(name) is not None}


def _dump(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _exclusive_create(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_dump(value))
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_checkpoint(path: Path, value: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".checkpoint-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_dump(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _assert_archive_url(value: str, allowed_hosts: set[str], endpoint: str) -> None:
    parsed = urllib.parse.urlsplit(value)
    expected = urllib.parse.urlsplit(endpoint)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or host not in allowed_hosts:
        raise ValueError("B4 archive-only guard rejected URL")
    if host == (expected.hostname or "").casefold() and parsed.path != expected.path:
        raise ValueError("B4 availability endpoint path changed")


def normalize_snapshot_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").casefold() != "web.archive.org":
        raise ValueError("Wayback response contains a non-archive snapshot URL")
    if not re.match(r"^/web/\d{14}/https?://", parsed.path):
        raise ValueError("Wayback response contains a malformed snapshot URL")
    return parsed._replace(scheme="https").geturl()


def parse_availability(payload: dict[str, Any]) -> dict[str, Any]:
    snapshots = payload.get("archived_snapshots")
    if not isinstance(snapshots, dict):
        raise ValueError("Wayback response lacks archived_snapshots")
    closest = snapshots.get("closest")
    if closest is None:
        return {"available": False, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None}
    if not isinstance(closest, dict):
        raise ValueError("Wayback closest snapshot is malformed")
    if closest.get("available") is not True:
        return {"available": False, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": str(closest.get("status") or "") or None}
    timestamp = str(closest.get("timestamp") or "")
    status = str(closest.get("status") or "")
    if not re.fullmatch(r"\d{14}", timestamp) or status != "200":
        raise ValueError("Available Wayback snapshot lacks a valid timestamp/status")
    return {"available": True, "snapshot_timestamp": timestamp, "snapshot_url": normalize_snapshot_url(str(closest.get("url") or "")), "snapshot_http_status": status}


def fetch_availability(url: str, contract: dict[str, Any], request_counter: list[int]) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed = {str(host).casefold().rstrip(".") for host in contract["allowed_network_hosts"]}
    endpoint = str(contract["endpoint"])
    opener = urllib.request.build_opener(NoRedirect())
    current = url
    redirects = 0
    while True:
        _assert_archive_url(current, allowed, endpoint)
        time.sleep(float(contract["minimum_delay_seconds"]))
        request = urllib.request.Request(current, headers=REQUEST_HEADERS, method="GET")
        request_counter[0] += 1
        try:
            response = opener.open(request, timeout=int(contract["timeout_seconds"]))
        except urllib.error.HTTPError as error:
            diagnostics = {"final_archive_url": current, "redirect_count": redirects, "http_status": int(error.code), "response_headers": _headers(error.headers)}
            if error.code == 429:
                raise AvailabilityRateLimitStop("Wayback availability endpoint returned HTTP 429", diagnostics) from error
            if error.code in {301, 302, 303, 307, 308}:
                if redirects >= int(contract["maximum_redirects"]):
                    raise AvailabilityResponseError("Maximum archive redirect count exceeded", diagnostics) from error
                location = error.headers.get("Location")
                if not location:
                    raise AvailabilityResponseError("Archive redirect omitted Location", diagnostics) from error
                current = urllib.parse.urljoin(current, location)
                _assert_archive_url(current, allowed, endpoint)
                redirects += 1
                continue
            raise AvailabilityResponseError(f"Unexpected HTTP status: {error.code}", diagnostics) from error
        with response:
            status = int(response.status)
            content_type = str(response.headers.get("Content-Type") or "")
            payload = response.read(int(contract["maximum_response_bytes"]) + 1)
            diagnostics = {
                "final_archive_url": current,
                "redirect_count": redirects,
                "http_status": status,
                "content_type": content_type,
                "response_bytes": len(payload),
                "response_sha256": hashlib.sha256(payload).hexdigest(),
                "response_headers": _headers(response.headers),
            }
        if status != 200:
            raise AvailabilityResponseError(f"Unexpected HTTP status: {status}", diagnostics)
        if len(payload) > int(contract["maximum_response_bytes"]):
            raise AvailabilityResponseError("Wayback availability response exceeds size limit", diagnostics)
        if not content_type.casefold().startswith(str(contract["required_content_type_prefix"]).casefold()):
            raise AvailabilityResponseError(f"Unexpected availability content type: {content_type}", diagnostics)
        try:
            value = json.loads(payload.decode("utf-8"))
        except Exception as error:
            raise AvailabilityResponseError(f"Invalid availability JSON: {type(error).__name__}: {error}", diagnostics) from error
        if not isinstance(value, dict):
            raise AvailabilityResponseError("Wayback availability response is not a JSON object", diagnostics)
        return value, diagnostics


def validate_static_inputs(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    check = verify_release(release_path, require_output_absent=True)
    release = load_object(release_path)
    qa = load_object(release_qa_path)
    if check["status"] != PASS_STATUS or check["errors"]:
        raise PermissionError("B4 release independent recomputation failed")
    if qa.get("status") != PASS_STATUS or qa.get("errors") != []:
        raise PermissionError("B4 release QA is not PASS")
    if qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise PermissionError("B4 release QA hash binding changed")
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    return release, plan


def dynamic_coordination_gate(release: dict[str, Any], current: datetime) -> dict[str, Any]:
    from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_result_v1 import verify as verify_a1_result

    contract = release["coordination_contract"]
    report_path = Path(contract["a1_final_report_path"])
    partial_path = report_path.with_suffix(report_path.suffix + ".partial")
    qa_path = Path(contract["a1_independent_result_qa_path"])
    if partial_path.exists():
        raise PermissionError("B4 is closed because the A1 partial journal exists")
    if not report_path.is_file() or not qa_path.is_file():
        raise PermissionError("B4 is closed until final A1 report and independent QA exist")
    root = Path(__file__).resolve().parents[1]
    a1_release_path = root / release["inputs"]["a1_cdx_release"]["path"]
    a1_release_qa_path = Path(release["inputs"]["a1_cdx_release_qa"]["path"])
    recomputed = verify_a1_result(a1_release_path, a1_release_qa_path, report_path)
    recorded = load_object(qa_path)
    if recomputed.get("errors") != [] or recorded.get("errors") != []:
        raise PermissionError("B4 is closed because A1 result QA has errors")
    if recomputed.get("status") not in set(contract["acceptable_a1_result_qa_statuses"]):
        raise PermissionError("B4 is closed because A1 did not complete successfully")
    for field in ("status", "inputs", "checks", "decision", "errors"):
        if recorded.get(field) != recomputed.get(field):
            raise PermissionError("B4 is closed because recorded A1 QA differs from recomputation")
    report = load_object(report_path)
    if report.get("stopped_on_http_429") is not False or report.get("error") is not None:
        raise PermissionError("B4 is closed because A1 preserved an error or HTTP 429")
    a1_created_at = datetime.fromisoformat(report["created_at"])
    if a1_created_at.tzinfo is None or current.tzinfo is None:
        raise PermissionError("B4 coordination timestamps must be timezone-aware")
    dynamic = a1_created_at + timedelta(seconds=int(contract["minimum_cooldown_seconds_after_latest_archive_request"]))
    floor = datetime.fromisoformat(contract["absolute_not_before_floor"])
    effective = max(dynamic, floor)
    if current < effective:
        raise PermissionError(f"B4 dynamic not-before gate is closed until {effective.isoformat()}")
    return {"a1_report_path": str(report_path), "a1_report_sha256": sha256_file(report_path), "a1_result_qa_path": str(qa_path), "a1_result_qa_sha256": sha256_file(qa_path), "a1_report_created_at": a1_created_at.isoformat(), "absolute_not_before_floor": floor.isoformat(), "effective_not_before": effective.isoformat()}


def _base_result(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("availability_plan_id", "candidate_id", "cohort", "channel_id", "channel_target_stratum", "candidate_host", "candidate_url", "target_timestamp")}


def run_plan(
    release_path: Path,
    release_qa_path: Path,
    release: dict[str, Any],
    plan: list[dict[str, Any]],
    output: Path,
    started_at: str,
    coordination: dict[str, Any],
    *,
    fetcher: Callable[[str, dict[str, Any], list[int]], tuple[dict[str, Any], dict[str, Any]]] = fetch_availability,
) -> dict[str, Any]:
    partial = output.with_suffix(output.suffix + release["planned_output"]["partial_journal_suffix"])
    if output.exists() or partial.exists():
        raise FileExistsError("Refusing to run B4: final or partial output already exists")
    pending = [row["availability_plan_id"] for row in plan]
    attempted: list[dict[str, Any]] = []
    journal = {
        "journal_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_EXECUTION_JOURNAL_V1",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": started_at,
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "coordination_evidence": coordination,
        "attempted_results": [],
        "attempted_availability_plan_ids": [],
        "pending_availability_plan_ids": pending,
        "logical_attempt_count": 0,
        "network_request_count": 0,
        "stopped_on_http_429": False,
        "resume_allowed": False,
        "safety_contract": {"candidate_live_domain_access_operations": 0, "archived_page_download_operations": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }
    _exclusive_create(partial, journal)
    request_counter = [0]
    stopped_on_429 = False
    fail_closed_stop = False
    for index, row in enumerate(plan):
        base = _base_result(row)
        try:
            payload, diagnostics = fetcher(row["planned_request_url"], release["execution_contract"], request_counter)
            parsed = parse_availability(payload)
            result = {**base, "queried": True, **parsed, "response_diagnostics": diagnostics, "error": None}
        except AvailabilityRateLimitStop as error:
            stopped_on_429 = True
            fail_closed_stop = True
            result = {**base, "queried": True, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": "429", "response_diagnostics": error.diagnostics, "error": f"{type(error).__name__}: {error}"}
        except AvailabilityResponseError as error:
            fail_closed_stop = True
            result = {**base, "queried": True, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": error.diagnostics.get("http_status"), "response_diagnostics": error.diagnostics, "error": f"{type(error).__name__}: {error}"}
        except Exception as error:
            fail_closed_stop = True
            result = {**base, "queried": True, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None, "response_diagnostics": {}, "error": f"{type(error).__name__}: {error}"}
        attempted.append(result)
        pending = [remaining["availability_plan_id"] for remaining in plan[index + 1 :]]
        journal.update({"attempted_results": attempted, "attempted_availability_plan_ids": [item["availability_plan_id"] for item in attempted], "pending_availability_plan_ids": pending, "logical_attempt_count": len(attempted), "network_request_count": request_counter[0], "stopped_on_http_429": stopped_on_429})
        _atomic_checkpoint(partial, journal)
        if fail_closed_stop:
            break
    attempted_ids = {row["availability_plan_id"] for row in attempted}
    results = list(attempted)
    for row in plan:
        if row["availability_plan_id"] not in attempted_ids:
            results.append({**_base_result(row), "queried": False, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None, "response_diagnostics": {}, "error": "NOT_QUERIED_AFTER_FAIL_CLOSED_STOP"})
    results.sort(key=lambda row: int(row["availability_plan_id"].rsplit("_", 1)[1]))
    unresolved = sum(row["error"] is not None for row in results)
    available = sum(row["available"] is True for row in results)
    unavailable = sum(row["available"] is False for row in results)
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "started_at": started_at,
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED",
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "plan_sha256": release["inputs"]["availability_plan"]["sha256"],
        "coordination_evidence": coordination,
        "requested_candidate_count": len(plan),
        "logical_attempt_count": len(attempted),
        "network_request_count": request_counter[0],
        "available_snapshot_count": available,
        "unavailable_snapshot_count": unavailable,
        "unresolved_error_count": unresolved,
        "stopped_on_http_429": stopped_on_429,
        "stopped_fail_closed": fail_closed_stop,
        "capture_plan_construction_ready": unresolved == 0,
        "results": results,
        "safety_contract": {"candidate_live_domain_access_operations": 0, "only_archive_availability_hosts_accessed": True, "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }
    _atomic_checkpoint(partial, report)
    partial.replace(output)
    return report


def execute(release_path: Path, release_qa_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release, plan = validate_static_inputs(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    coordination = dynamic_coordination_gate(release, current)
    return run_plan(release_path, release_qa_path, release, plan, Path(release["planned_output"]["path"]), current.isoformat(), coordination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release, plan = validate_static_inputs(args.release, args.release_qa)
    if args.verify_only:
        print(json.dumps({"valid": True, "release_id": release["release_id"], "plan_rows": len(plan), "network_execution_allowed_now": False, "dynamic_a1_cooldown_required": True}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "requested_candidate_count", "logical_attempt_count", "network_request_count", "available_snapshot_count", "unavailable_snapshot_count", "unresolved_error_count", "stopped_on_http_429", "capture_plan_construction_ready")}, ensure_ascii=False, indent=2))
    return 0 if report["capture_plan_construction_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
