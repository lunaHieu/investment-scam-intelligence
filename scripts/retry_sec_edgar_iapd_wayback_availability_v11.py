"""Policy-compliant crash-safe executor for a future frozen V11 release.

V11 is a new implementation; it does not call the V10 executor. It preserves
current archive-identification and response-diagnostic requirements and retries
only the two exact external-holdout rows frozen by the V11 protocol.
"""

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
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.execute_sec_edgar_iapd_wayback_availability_v1 import NoRedirect, parse_response
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


AUTHORITATIVE_MODULE = "scripts.retry_sec_edgar_iapd_wayback_availability_v11"
USER_AGENT = (
    "ISI-Research/2.0 "
    "(gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"
)
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
PRESERVED_HEADERS = (
    "Retry-After",
    "Date",
    "Server",
    "Content-Type",
    "X-Archive-Wayback-Runtime-Error",
)


class AvailabilityResponseError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class AvailabilityRateLimitStop(AvailabilityResponseError):
    """HTTP 429 stops the remaining exact-two-row retry."""


def _headers(headers: Any) -> dict[str, str]:
    return {
        name: str(headers.get(name))
        for name in PRESERVED_HEADERS
        if headers is not None and headers.get(name) is not None
    }


def _assert_archive_url(value: str, allowed_hosts: set[str]) -> None:
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or host not in allowed_hosts:
        raise ValueError("V11 archive-only network guard rejected a URL")


def request_url(endpoint: str, candidate_url: str, target_timestamp: str) -> str:
    return endpoint + "?" + urllib.parse.urlencode(
        {"url": candidate_url, "timestamp": target_timestamp}
    )


def fetch_availability(
    url: str,
    contract: dict[str, Any],
    request_counter: list[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed = {str(host).casefold() for host in contract["allowed_network_hosts"]}
    opener = urllib.request.build_opener(NoRedirect())
    current = url
    redirects = 0
    while True:
        _assert_archive_url(current, allowed)
        time.sleep(float(contract["minimum_delay_seconds"]))
        request = urllib.request.Request(current, headers=REQUEST_HEADERS, method="GET")
        request_counter[0] += 1
        try:
            response = opener.open(request, timeout=int(contract["timeout_seconds"]))
        except urllib.error.HTTPError as error:
            diagnostics = {
                "final_archive_url": current,
                "redirect_count": redirects,
                "http_status": int(error.code),
                "response_headers": _headers(error.headers),
            }
            if error.code == 429:
                raise AvailabilityRateLimitStop(
                    "Wayback availability endpoint returned HTTP 429", diagnostics
                ) from error
            if error.code in {301, 302, 303, 307, 308}:
                if redirects >= int(contract["maximum_redirects"]):
                    raise AvailabilityResponseError(
                        "Maximum archive redirect count exceeded", diagnostics
                    ) from error
                location = error.headers.get("Location")
                if not location:
                    raise AvailabilityResponseError(
                        "Archive redirect omitted Location", diagnostics
                    ) from error
                current = urllib.parse.urljoin(current, location)
                _assert_archive_url(current, allowed)
                redirects += 1
                continue
            raise AvailabilityResponseError(
                f"Unexpected HTTP status: {error.code}", diagnostics
            ) from error
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
            raise AvailabilityResponseError(
                "Wayback availability response exceeds the size limit", diagnostics
            )
        if not content_type.casefold().startswith("application/json"):
            raise AvailabilityResponseError(
                f"Unexpected availability content type: {content_type}", diagnostics
            )
        try:
            value = json.loads(payload.decode("utf-8"))
        except Exception as error:
            raise AvailabilityResponseError(
                f"Invalid availability JSON: {type(error).__name__}: {error}", diagnostics
            ) from error
        if not isinstance(value, dict):
            raise AvailabilityResponseError(
                "Wayback availability response is not a JSON object", diagnostics
            )
        return value, diagnostics


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


def validate_inputs(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from scripts.verify_sec_edgar_iapd_wayback_availability_release_v11 import (
        PASS_STATUS,
        verify,
    )

    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    check = verify(release_path, require_output_absent=False)
    if check["errors"]:
        raise PermissionError("V11 release independent recomputation failed")
    if release_qa.get("status") != PASS_STATUS or release_qa.get("errors") != []:
        raise PermissionError("V11 release QA is not PASS")
    if release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise PermissionError("V11 release QA hash binding changed")
    root = release_path.resolve().parents[1]
    protocol = load_object(root / release["inputs"]["protocol"]["path"])
    parent = load_object(Path(protocol["inputs"]["availability_report_v10"]["path"]))
    return release, protocol, parent


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
    release_qa_path: Path,
    release: dict[str, Any],
    started_at: str,
    attempted: list[dict[str, Any]],
    pending_ids: list[str],
    request_count: int,
    stopped: bool,
) -> dict[str, Any]:
    return {
        "journal_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_V11_EXECUTION_JOURNAL",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": started_at,
        "executor": AUTHORITATIVE_MODULE,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "attempted_retry_results": deepcopy(attempted),
        "attempted_availability_plan_ids": [row["availability_plan_id"] for row in attempted],
        "pending_availability_plan_ids": list(pending_ids),
        "network_request_count_this_attempt": request_count,
        "stopped_on_http_429": stopped,
        "resume_allowed": False,
        "request_policy": {
            "descriptive_user_agent": USER_AGENT,
            "diagnostic_headers_preserved": list(PRESERVED_HEADERS),
            "automatic_retry_allowed": False,
        },
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
    release_qa_path: Path,
    now: datetime | None = None,
    *,
    fetcher: Callable[[str, dict[str, Any], list[int]], tuple[dict[str, Any], dict[str, Any]]] = fetch_availability,
    after_checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    release, protocol, parent = validate_inputs(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    not_before = datetime.fromisoformat(release["cooldown_contract"]["not_before"])
    if current.tzinfo is None or current < not_before:
        raise PermissionError("V11 not-before gate is closed")
    output = Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("Refusing to run: V11 final or partial output already exists")

    retry_rows = release["ordered_retry_rows"]
    pending_ids = [row["availability_plan_id"] for row in retry_rows]
    attempted: list[dict[str, Any]] = []
    request_counter = [0]
    stopped = False
    started_at = current.isoformat()
    reservation = _journal(
        release_path, release_qa_path, release, started_at, attempted, pending_ids, 0, False
    )
    _exclusive_create(partial, reservation)
    contract = release["network_contract"]

    for source in retry_rows:
        identifier = source["availability_plan_id"]
        base = _base_result(source)
        diagnostics: dict[str, Any] = {}
        try:
            payload, diagnostics = fetcher(
                request_url(contract["endpoint"], source["candidate_url"], source["query_timestamp"]),
                contract,
                request_counter,
            )
            result = {
                **base,
                "queried": True,
                **parse_response(payload),
                "response_diagnostics": diagnostics,
                "error": None,
            }
        except AvailabilityRateLimitStop as error:
            stopped = True
            result = {
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": "429",
                "response_diagnostics": error.diagnostics,
                "error": f"{type(error).__name__}: {error}",
            }
        except AvailabilityResponseError as error:
            result = {
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": str(error.diagnostics.get("http_status") or "") or None,
                "response_diagnostics": error.diagnostics,
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
                "response_diagnostics": diagnostics,
                "error": f"{type(error).__name__}: {error}",
            }
        attempted.append(result)
        pending_ids.remove(identifier)
        checkpoint = _journal(
            release_path,
            release_qa_path,
            release,
            started_at,
            attempted,
            pending_ids,
            request_counter[0],
            stopped,
        )
        _atomic_checkpoint(partial, checkpoint)
        if after_checkpoint is not None:
            after_checkpoint(deepcopy(checkpoint))
        if stopped:
            break

    attempted_by_id = {row["availability_plan_id"]: row for row in attempted}
    final_results: list[dict[str, Any]] = []
    for old in parent["results"]:
        identifier = old["availability_plan_id"]
        if old.get("error") is None:
            final_results.append(deepcopy(old))
        elif identifier in attempted_by_id:
            final_results.append(attempted_by_id[identifier])
        else:
            source = next(row for row in retry_rows if row["availability_plan_id"] == identifier)
            final_results.append(
                {
                    **_base_result(source),
                    "queried": False,
                    "available": None,
                    "snapshot_timestamp": None,
                    "snapshot_url": None,
                    "snapshot_http_status": None,
                    "response_diagnostics": {},
                    "error": "NOT_REQUERIED_AFTER_HTTP_429_STOP_V11",
                }
            )
    unresolved = sum(row.get("error") is not None for row in final_results)
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED",
        "executor": AUTHORITATIVE_MODULE,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "parent_report_path": protocol["inputs"]["availability_report_v10"]["path"],
        "parent_report_sha256": protocol["inputs"]["availability_report_v10"]["sha256"],
        "requested_candidate_count": 115,
        "resolved_results_reused_from_v10": 113,
        "retry_candidate_count": 2,
        "retried_availability_plan_ids": [row["availability_plan_id"] for row in attempted],
        "logical_retry_attempt_count": len(attempted),
        "network_request_count_this_attempt": request_counter[0],
        "cumulative_network_request_count": parent["cumulative_network_request_count"] + request_counter[0],
        "available_snapshot_count": sum(row.get("available") is True for row in final_results),
        "unavailable_snapshot_count": sum(row.get("available") is False for row in final_results),
        "unresolved_error_count": unresolved,
        "stopped_on_http_429": stopped,
        "supplemental_availability_complete": unresolved == 0,
        "original_capture_plan_mutation_allowed": False,
        "results": final_results,
        "request_policy": reservation["request_policy"],
        "safety_contract": reservation["safety_contract"],
    }
    _atomic_checkpoint(partial, report)
    os.replace(partial, output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release, _, _ = validate_inputs(args.release, args.release_qa)
    if args.verify_only:
        remaining = max(
            0,
            round(
                (
                    datetime.fromisoformat(release["cooldown_contract"]["not_before"])
                    - datetime.now(timezone.utc).astimezone()
                ).total_seconds()
            ),
        )
        print(
            json.dumps(
                {
                    "valid": True,
                    "release_id": release["release_id"],
                    "retry_rows": 2,
                    "seconds_until_not_before": remaining,
                    "authoritative_executor": AUTHORITATIVE_MODULE,
                    "descriptive_user_agent": USER_AGENT,
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.release, args.release_qa)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "report_id",
                    "status",
                    "logical_retry_attempt_count",
                    "network_request_count_this_attempt",
                    "unresolved_error_count",
                    "stopped_on_http_429",
                    "supplemental_availability_complete",
                )
            },
            indent=2,
        )
    )
    return 0 if report["supplemental_availability_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
