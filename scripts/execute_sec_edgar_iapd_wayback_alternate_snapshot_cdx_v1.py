"""Crash-safe executor for the frozen one-row alternate-snapshot CDX release.

This module enumerates archive metadata only.  It never contacts the candidate
domain and never downloads an archived page.  A selected CDX row is merely a
candidate for a later, separately frozen capture release.
"""

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.capture_balanced_wayback_plan_v2 import NoRedirect
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


EXECUTOR = "scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1"
USER_AGENT = (
    "ISI-Research/2.0 "
    "(gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}
PRESERVED_HEADERS = (
    "Retry-After",
    "Date",
    "Server",
    "Content-Type",
    "X-Archive-Wayback-Runtime-Error",
)
DIGEST_RE = re.compile(r"^[A-Z2-7]{32}$", re.IGNORECASE)


class CdxResponseError(RuntimeError):
    """A CDX response violated the frozen contract."""

    def __init__(self, message: str, diagnostics: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class CdxRateLimitStop(CdxResponseError):
    """HTTP 429 requires an immediate stop without an automatic retry."""


def _headers(headers: Any) -> dict[str, str]:
    return {
        name: str(headers.get(name))
        for name in PRESERVED_HEADERS
        if headers is not None and headers.get(name) is not None
    }


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


def _assert_cdx_url(url: str, contract: dict[str, Any]) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError("CDX request must use HTTPS")
    if parsed.hostname not in set(contract["allowed_network_hosts"]):
        raise ValueError("CDX request host is outside the frozen allowlist")
    endpoint = urllib.parse.urlsplit(contract["endpoint"])
    if parsed.hostname != endpoint.hostname or parsed.path != endpoint.path:
        raise ValueError("CDX request endpoint changed")


def build_request_url(contract: dict[str, Any]) -> str:
    query = contract["query"]
    pairs: list[tuple[str, str]] = [
        ("url", str(query["url"])),
        ("matchType", str(query["matchType"])),
        ("output", str(query["output"])),
        ("fl", ",".join(query["fields"])),
    ]
    for value in query["filters"]:
        pairs.append(("filter", str(value)))
    pairs.extend(
        [
            ("filter", f"timestamp:!{timestamp}")
            for timestamp in query["excluded_snapshot_timestamps"]
        ]
    )
    pairs.append(("limit", str(query["maximum_rows"])))
    url = contract["endpoint"] + "?" + urllib.parse.urlencode(pairs)
    _assert_cdx_url(url, contract)
    return url


def fetch_cdx(
    url: str,
    contract: dict[str, Any],
    request_counter: list[int],
) -> tuple[bytes, dict[str, Any]]:
    """Perform one CDX metadata request and retain bounded diagnostics."""

    _assert_cdx_url(url, contract)
    time.sleep(float(contract["minimum_delay_seconds"]))
    request = urllib.request.Request(url, headers=REQUEST_HEADERS, method="GET")
    request_counter[0] += 1
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=int(contract["timeout_seconds"]))
    except urllib.error.HTTPError as error:
        diagnostics = {
            "http_status": int(error.code),
            "response_headers": _headers(error.headers),
        }
        if error.code == 429:
            raise CdxRateLimitStop("HTTP 429 from the CDX endpoint", diagnostics) from error
        raise CdxResponseError(f"Unexpected HTTP status: {error.code}", diagnostics) from error
    with response:
        status = int(response.status)
        content_type = str(response.headers.get("Content-Type") or "")
        payload = response.read(int(contract["maximum_response_bytes"]) + 1)
        diagnostics = {
            "http_status": status,
            "content_type": content_type,
            "response_bytes": len(payload),
            "response_sha256": hashlib.sha256(payload).hexdigest(),
            "response_headers": _headers(response.headers),
        }
    if status != 200:
        raise CdxResponseError(f"Unexpected HTTP status: {status}", diagnostics)
    if len(payload) > int(contract["maximum_response_bytes"]):
        raise CdxResponseError("CDX response exceeds the frozen size bound", diagnostics)
    if not content_type.casefold().startswith("application/json"):
        raise CdxResponseError(f"Unexpected CDX content type: {content_type}", diagnostics)
    return payload, diagnostics


def _canonical_original(value: str) -> tuple[str, str] | None:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    if parsed.query or parsed.fragment:
        return None
    return host, path


def parse_and_select(payload: bytes, release: dict[str, Any]) -> dict[str, Any]:
    """Parse CDX JSON and select one alternate row without reading page content."""

    contract = release["cdx_contract"]
    fields = contract["query"]["fields"]
    try:
        table = json.loads(payload.decode("utf-8"))
    except Exception as error:
        raise ValueError(f"Invalid CDX JSON: {type(error).__name__}: {error}") from error
    if not isinstance(table, list) or not table:
        raise ValueError("CDX response must be a non-empty JSON table")
    if table[0] != fields:
        raise ValueError("CDX response header differs from the frozen field order")
    if len(table) - 1 > int(contract["query"]["maximum_rows"]):
        raise ValueError("CDX response row count exceeds the frozen limit")

    record = release["target_record"]
    expected_host = record["candidate_host"].casefold()
    excluded = set(record["excluded_snapshot_timestamps"])
    eligible: list[dict[str, str]] = []
    rejected: list[dict[str, Any]] = []
    for ordinal, values in enumerate(table[1:], start=1):
        reason = None
        if not isinstance(values, list) or len(values) != len(fields):
            rejected.append({"ordinal": ordinal, "reason": "MALFORMED_ROW"})
            continue
        row = {field: str(value) for field, value in zip(fields, values)}
        canonical = _canonical_original(row["original"])
        if not re.fullmatch(r"\d{14}", row["timestamp"]):
            reason = "INVALID_TIMESTAMP"
        elif row["timestamp"] in excluded:
            reason = "EXCLUDED_FAILED_TIMESTAMP"
        elif canonical != (expected_host, "/"):
            reason = "ORIGINAL_OUTSIDE_FROZEN_TARGET"
        elif row["statuscode"] != "200":
            reason = "NON_200_STATUS"
        elif row["mimetype"].casefold() not in set(contract["eligible_mimetypes"]):
            reason = "INELIGIBLE_MIMETYPE"
        elif not DIGEST_RE.fullmatch(row["digest"]):
            reason = "INVALID_OR_MISSING_DIGEST"
        if reason:
            rejected.append({"ordinal": ordinal, "reason": reason, **row})
        else:
            eligible.append(row)

    anchor = datetime.strptime(record["failed_snapshot_timestamp"], "%Y%m%d%H%M%S")

    def key(row: dict[str, str]) -> tuple[float, int, str, str]:
        stamp = datetime.strptime(row["timestamp"], "%Y%m%d%H%M%S")
        distance = abs((stamp - anchor).total_seconds())
        # At equal distance, an earlier snapshot precedes a later snapshot.
        return distance, int(row["timestamp"]), row["original"], row["digest"]

    eligible.sort(key=key)
    selected = dict(eligible[0]) if eligible else None
    if selected is not None:
        selected["requested_archive_url"] = (
            f"https://web.archive.org/web/{selected['timestamp']}id_/{selected['original']}"
        )
        selected["selection_rank"] = 1
    return {
        "returned_row_count": len(table) - 1,
        "eligible_row_count": len(eligible),
        "rejected_row_count": len(rejected),
        "eligible_rows": eligible,
        "rejected_rows": rejected,
        "selected_candidate": selected,
        "selection_rule": contract["selection_rule"],
    }


def validate_inputs(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1 import verify

    release = load_object(release_path)
    qa = load_object(release_qa_path)
    checked = verify(release_path, require_output_absent=False)
    if checked["errors"]:
        raise PermissionError("CDX release independent recomputation failed")
    if qa.get("status") != checked["status"] or qa.get("errors") != []:
        raise PermissionError("CDX release QA is not authoritative PASS")
    if qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise PermissionError("CDX release QA hash binding changed")
    return release, qa


def execute(
    release_path: Path,
    release_qa_path: Path,
    now: datetime | None = None,
    *,
    fetcher: Callable[[str, dict[str, Any], list[int]], tuple[bytes, dict[str, Any]]] = fetch_cdx,
) -> dict[str, Any]:
    release, _ = validate_inputs(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    not_before = datetime.fromisoformat(release["cooldown_contract"]["not_before"])
    if current.tzinfo is None or current < not_before:
        raise PermissionError("Alternate-snapshot CDX not-before gate is closed")
    output = Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("Refusing to run: CDX final or partial output already exists")

    started_at = current.isoformat()
    reservation = {
        "journal_id": "ISI_SEC_EDGAR_IAPD_ALTERNATE_SNAPSHOT_CDX_JOURNAL_V1",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": started_at,
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "target_availability_plan_id": release["target_record"]["availability_plan_id"],
        "network_request_count": 0,
        "resume_allowed": False,
        "candidate_live_domain_access_operations": 0,
        "archived_page_download_operations": 0,
    }
    _exclusive_create(partial, reservation)
    request_count = [0]
    stopped = False
    diagnostics: dict[str, Any] = {}
    error_text: str | None = None
    parsed: dict[str, Any] | None = None
    try:
        request_url = build_request_url(release["cdx_contract"])
        payload, diagnostics = fetcher(request_url, release["cdx_contract"], request_count)
        parsed = parse_and_select(payload, release)
    except CdxRateLimitStop as error:
        stopped = True
        diagnostics = error.diagnostics
        error_text = f"{type(error).__name__}: {error}"
    except CdxResponseError as error:
        diagnostics = error.diagnostics
        error_text = f"{type(error).__name__}: {error}"
    except Exception as error:
        error_text = f"{type(error).__name__}: {error}"

    selected = parsed.get("selected_candidate") if parsed else None
    if error_text:
        status = "INCOMPLETE_ERROR_PRESERVED"
    elif selected is None:
        status = "COMPLETE_NO_ELIGIBLE_ALTERNATE_QUARANTINE_REMAINS"
    else:
        status = "COMPLETE_ALTERNATE_CANDIDATE_SELECTED_CAPTURE_NOT_AUTHORIZED"
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": status,
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "target_availability_plan_id": release["target_record"]["availability_plan_id"],
        "failed_snapshot_timestamp_excluded": release["target_record"]["failed_snapshot_timestamp"],
        "network_request_count": request_count[0],
        "stopped_on_http_429": stopped,
        "response_diagnostics": diagnostics,
        "error": error_text,
        "enumeration": parsed,
        "decision": {
            "alternate_capture_release_may_be_prepared": selected is not None and error_text is None,
            "alternate_capture_is_authorized": False,
            "same_failed_timestamp_may_be_used": False,
            "original_review_population_may_be_mutated": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "archive_metadata_requests": request_count[0],
            "archived_page_download_operations": 0,
            "raw_files_written": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
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
    release, _ = validate_inputs(args.release, args.release_qa)
    if args.verify_only:
        not_before = datetime.fromisoformat(release["cooldown_contract"]["not_before"])
        remaining = max(
            0,
            round((not_before - datetime.now(timezone.utc).astimezone()).total_seconds()),
        )
        print(
            json.dumps(
                {
                    "valid": True,
                    "release_id": release["release_id"],
                    "target_rows": 1,
                    "network_requests_per_execution_maximum": 1,
                    "seconds_until_not_before": remaining,
                    "authoritative_executor": EXECUTOR,
                    "descriptive_user_agent": USER_AGENT,
                    "archived_page_download_allowed": False,
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
                    "stopped_on_http_429",
                )
            },
            indent=2,
        )
    )
    return 0 if report["error"] is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
