"""Policy-compliant crash-safe executor for the frozen one-row capture retry.

V2 preserves the V1 release and result contract, but identifies the automated
client as required by the current Internet Archive policy and retains selected
rate-limit response headers for diagnosis. It never retries inside one run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.build_sec_edgar_iapd_wayback_capture_release_v1 import parse_time
from scripts.capture_balanced_wayback_plan_v2 import NoRedirect, assert_archive_url
from scripts.execute_sec_edgar_iapd_wayback_capture_retry_v1 import (
    ResponseValidationError,
    _checkpoint,
    _headers,
    _write_exclusive,
    capture_row as capture_row_v1,
    validate_inputs,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


EXECUTOR = "scripts.execute_sec_edgar_iapd_wayback_capture_retry_v2"
USER_AGENT = (
    "ISI-Research/2.0 "
    "(gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
}


def fetch_retry(
    url: str,
    contract: dict[str, Any],
    request_counter: list[int],
) -> tuple[bytes, dict[str, Any]]:
    """Fetch once per permitted archive URL and preserve diagnostic headers."""

    opener = urllib.request.build_opener(NoRedirect())
    current = url
    redirects = 0
    while True:
        assert_archive_url(current)
        time.sleep(float(contract["minimum_delay_seconds"]))
        request = urllib.request.Request(current, headers=REQUEST_HEADERS, method="GET")
        request_counter[0] += 1
        try:
            response = opener.open(request, timeout=int(contract["timeout_seconds"]))
        except urllib.error.HTTPError as error:
            if error.code in {301, 302, 303, 307, 308}:
                diagnostics = {
                    "http_status": error.code,
                    "response_headers": _headers(error.headers),
                }
                if redirects >= int(contract["maximum_redirects"]):
                    raise ResponseValidationError(
                        "Maximum archive redirect count exceeded", diagnostics
                    ) from error
                location = error.headers.get("Location")
                if not location:
                    raise ResponseValidationError(
                        f"HTTP {error.code} without redirect location", diagnostics
                    ) from error
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
        diagnostics = {
            "final_archive_url": current,
            "redirect_count": redirects,
            "http_status": status,
            "content_type": content_type,
            "response_bytes": len(payload),
            "response_sha256": hashlib.sha256(payload).hexdigest(),
            "response_headers": response_headers,
        }
        if status != 200:
            raise ResponseValidationError(f"Unexpected HTTP status: {status}", diagnostics)
        if not content_type.casefold().startswith(
            str(contract["required_content_type_prefix"]).casefold()
        ):
            raise ResponseValidationError(f"Unexpected content type: {content_type}", diagnostics)
        if len(payload) > int(contract["maximum_response_bytes"]):
            raise ResponseValidationError("Archived HTML capture exceeds the size limit", diagnostics)
        if len(payload) < 1024:
            raise ResponseValidationError(
                f"Archived HTML capture is unexpectedly small: {len(payload)} bytes",
                diagnostics,
            )
        return payload, diagnostics


def capture_row(
    row: dict[str, Any],
    contract: dict[str, Any],
    fetcher: Callable[..., tuple[bytes, dict[str, Any]]] = fetch_retry,
) -> tuple[dict[str, Any], int]:
    return capture_row_v1(row, contract, fetcher)


def execute(
    release_path: Path,
    release_qa_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    release, _ = validate_inputs(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None or current < parse_time(release["execution_contract"]["not_before"]):
        raise PermissionError("Capture retry not-before gate is closed")
    output = Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("Refusing to run: retry final or partial output already exists")
    reservation = {
        "journal_id": "ISI_SEC_EDGAR_IAPD_CAPTURE_RETRY_JOURNAL_V2",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": current.isoformat(),
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "pending_availability_plan_ids": [release["retry_rows"][0]["availability_plan_id"]],
        "attempted_results": [],
        "network_request_count": 0,
        "resume_allowed": False,
        "request_policy": {
            "descriptive_user_agent": USER_AGENT,
            "retry_after_header_preserved": True,
            "automatic_retry_allowed": False,
        },
    }
    _write_exclusive(partial, reservation)
    result, request_count = capture_row(
        release["retry_rows"][0], release["execution_contract"]
    )
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if result["outcome"] == "CAPTURED" else "INCOMPLETE_FAILURE_PRESERVED",
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "planned_capture_count": 1,
        "network_request_count": request_count,
        "captured_count": int(result["outcome"] == "CAPTURED"),
        "failed_count": int(result["outcome"] == "FAILED"),
        "stopped_on_http_429": result.get("http_status") == 429,
        "request_policy": reservation["request_policy"],
        "results": [result],
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
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
        remaining = max(
            0,
            round(
                (
                    parse_time(release["execution_contract"]["not_before"])
                    - datetime.now(timezone.utc).astimezone()
                ).total_seconds()
            ),
        )
        print(
            json.dumps(
                {
                    "valid": True,
                    "release_id": release["release_id"],
                    "retry_capture_count": 1,
                    "seconds_until_not_before": remaining,
                    "authoritative_executor": EXECUTOR,
                    "descriptive_user_agent": USER_AGENT,
                    "retry_after_header_preserved": True,
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
                    "network_request_count",
                    "captured_count",
                    "failed_count",
                    "stopped_on_http_429",
                )
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
