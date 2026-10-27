"""Execute the frozen one-row ready-channel CDX metadata canary."""

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
from scripts.verify_target_text_corpus_v1_ready_channel_cdx_canary_release_v1 import (
    PASS_STATUS,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


EXECUTOR = "scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1"
USER_AGENT = (
    "ISI-Research/2.1 (gpt-5; "
    "https://github.com/lunaHieu/investment-scam-intelligence)"
)
PRESERVED_HEADERS = (
    "Retry-After",
    "Date",
    "Server",
    "Content-Type",
    "X-Archive-Wayback-Runtime-Error",
)
DIGEST_RE = re.compile(r"^[A-Z2-7]{32}$", re.IGNORECASE)


class CanaryHttpError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any], payload: bytes | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics
        self.payload = payload


class CanaryRateLimitStop(CanaryHttpError):
    pass


def _headers(headers: Any) -> dict[str, str]:
    return {
        name: str(headers.get(name))
        for name in PRESERVED_HEADERS
        if headers is not None and headers.get(name) is not None
    }


def _dump(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _exclusive_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def build_request_url(contract: dict[str, Any]) -> str:
    query = contract["query"]
    pairs: list[tuple[str, str]] = [
        ("url", str(query["url"])),
        ("matchType", str(query["matchType"])),
        ("output", str(query["output"])),
        ("fl", ",".join(query["fields"])),
    ]
    pairs.extend(("filter", str(value)) for value in query["filters"])
    pairs.append(("limit", str(query["maximum_rows"])))
    url = contract["endpoint"] + "?" + urllib.parse.urlencode(pairs)
    parsed = urllib.parse.urlsplit(url)
    endpoint = urllib.parse.urlsplit(contract["endpoint"])
    if (
        parsed.scheme != "https"
        or parsed.hostname not in set(contract["allowed_network_hosts"])
        or parsed.hostname != endpoint.hostname
        or parsed.path != endpoint.path
    ):
        raise ValueError("CDX canary request escaped the frozen endpoint allowlist")
    return url


def fetch_cdx(
    url: str,
    contract: dict[str, Any],
    request_counter: list[int],
) -> tuple[bytes, dict[str, Any]]:
    time.sleep(float(contract["minimum_delay_seconds"]))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        method="GET",
    )
    request_counter[0] += 1
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=int(contract["timeout_seconds"]))
    except urllib.error.HTTPError as error:
        payload = error.read(int(contract["maximum_response_bytes"]) + 1) if error.fp else b""
        diagnostics = {
            "http_status": int(error.code),
            "response_bytes": len(payload),
            "response_sha256": hashlib.sha256(payload).hexdigest(),
            "response_headers": _headers(error.headers),
        }
        if error.code == 429:
            raise CanaryRateLimitStop("HTTP 429 from CDX canary endpoint", diagnostics, payload) from error
        raise CanaryHttpError(f"Unexpected HTTP status: {error.code}", diagnostics, payload) from error
    with response:
        payload = response.read(int(contract["maximum_response_bytes"]) + 1)
        diagnostics = {
            "http_status": int(response.status),
            "content_type": str(response.headers.get("Content-Type") or ""),
            "response_bytes": len(payload),
            "response_sha256": hashlib.sha256(payload).hexdigest(),
            "response_headers": _headers(response.headers),
        }
    if diagnostics["http_status"] != 200:
        raise CanaryHttpError("Unexpected CDX canary status", diagnostics, payload)
    if len(payload) > int(contract["maximum_response_bytes"]):
        raise CanaryHttpError("CDX canary response exceeds size bound", diagnostics, payload)
    return payload, diagnostics


def _canonical(value: str) -> tuple[str, str] | None:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if parsed.query or parsed.fragment:
        return None
    return host, parsed.path or "/"


def parse_metadata(payload: bytes, release: dict[str, Any]) -> dict[str, Any]:
    contract = release["cdx_contract"]
    fields = contract["query"]["fields"]
    try:
        table = json.loads(payload.decode("utf-8"))
    except Exception as error:
        raise ValueError(f"Invalid CDX JSON: {type(error).__name__}: {error}") from error
    if table == []:
        return {
            "valid_json": True,
            "returned_row_count": 0,
            "eligible_row_count": 0,
            "rejected_row_count": 0,
            "eligible_rows": [],
            "rejected_rows": [],
            "selected_candidate": None,
        }
    if not isinstance(table, list) or not table or table[0] != fields:
        raise ValueError("CDX response is not the frozen JSON table shape")
    if len(table) - 1 > int(contract["query"]["maximum_rows"]):
        raise ValueError("CDX response row count exceeds the frozen bound")
    expected_host = release["target_record"]["candidate_host"].casefold()
    eligible: list[dict[str, str]] = []
    rejected: list[dict[str, Any]] = []
    for ordinal, values in enumerate(table[1:], start=1):
        if not isinstance(values, list) or len(values) != len(fields):
            rejected.append({"ordinal": ordinal, "reason": "MALFORMED_ROW"})
            continue
        row = {field: str(value) for field, value in zip(fields, values)}
        reason = None
        if not re.fullmatch(r"\d{14}", row["timestamp"]):
            reason = "INVALID_TIMESTAMP"
        elif _canonical(row["original"]) != (expected_host, "/"):
            reason = "ORIGINAL_OUTSIDE_FROZEN_TARGET"
        elif row["statuscode"] != "200":
            reason = "NON_200_STATUS"
        elif row["mimetype"].casefold() != "text/html":
            reason = "INELIGIBLE_MIMETYPE"
        elif not DIGEST_RE.fullmatch(row["digest"]):
            reason = "INVALID_OR_MISSING_DIGEST"
        if reason:
            rejected.append({"ordinal": ordinal, "reason": reason, **row})
        else:
            eligible.append(row)
    anchor = release["target_record"]["target_timestamp"] + "000000"
    eligible.sort(
        key=lambda row: (
            abs(int(row["timestamp"]) - int(anchor)),
            int(row["timestamp"]),
            row["original"],
            row["digest"],
        )
    )
    selected = dict(eligible[0]) if eligible else None
    if selected is not None:
        selected["requested_archive_url"] = (
            f"https://web.archive.org/web/{selected['timestamp']}id_/{selected['original']}"
        )
    return {
        "valid_json": True,
        "returned_row_count": len(table) - 1,
        "eligible_row_count": len(eligible),
        "rejected_row_count": len(rejected),
        "eligible_rows": eligible,
        "rejected_rows": rejected,
        "selected_candidate": selected,
    }


def validate_inputs(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    release = load_object(release_path)
    qa = load_object(release_qa_path)
    checked = verify_release(release_path, require_output_absent=False)
    if checked.get("status") != PASS_STATUS or checked.get("errors"):
        raise PermissionError("Ready-channel CDX canary release recomputation failed")
    if qa.get("status") != PASS_STATUS or qa.get("errors") != []:
        raise PermissionError("Ready-channel CDX canary release QA is not authoritative PASS")
    if qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise PermissionError("Ready-channel CDX canary QA hash binding changed")
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
    not_before = datetime.fromisoformat(release["adaptive_gate"]["not_before"])
    if current.tzinfo is None or current < not_before:
        raise PermissionError("Ready-channel CDX canary not-before gate is closed")
    output = Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    raw = Path(release["planned_output"]["raw_response_path"])
    if output.exists() or partial.exists() or raw.exists():
        raise FileExistsError("Refusing to run: canary final, partial or raw output exists")

    reservation = {
        "journal_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_CANARY_JOURNAL_V1",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": current.isoformat(),
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "target_availability_plan_id": release["target_record"]["availability_plan_id"],
        "network_request_count": 0,
        "resume_allowed": False,
        "candidate_live_domain_access_operations": 0,
        "archived_page_download_operations": 0,
    }
    _exclusive_bytes(partial, _dump(reservation))
    request_count = [0]
    payload: bytes | None = None
    diagnostics: dict[str, Any] = {}
    parsed: dict[str, Any] | None = None
    error_text: str | None = None
    outcome = "INCOMPLETE_ERROR_PRESERVED_CDX_PATH_QUARANTINED"
    try:
        payload, diagnostics = fetcher(build_request_url(release["cdx_contract"]), release["cdx_contract"], request_count)
        parsed = parse_metadata(payload, release)
        outcome = (
            "COMPLETE_VALID_CDX_CANARY_WITH_ELIGIBLE_METADATA"
            if parsed["eligible_row_count"] > 0
            else "COMPLETE_VALID_CDX_CANARY_EMPTY_NO_ELIGIBLE_SNAPSHOT"
        )
    except CanaryRateLimitStop as error:
        payload = error.payload
        diagnostics = error.diagnostics
        error_text = f"{type(error).__name__}: {error}"
        outcome = "INCOMPLETE_HTTP_429_ARCHIVE_PROVIDER_CIRCUIT_OPEN"
    except CanaryHttpError as error:
        payload = error.payload
        diagnostics = error.diagnostics
        error_text = f"{type(error).__name__}: {error}"
    except ValueError as error:
        error_text = f"{type(error).__name__}: {error}"
        outcome = "INCOMPLETE_INVALID_CONTENT_PRESERVED_OFFLINE_RECONCILIATION_REQUIRED"
    except Exception as error:
        error_text = f"{type(error).__name__}: {error}"

    raw_record = None
    if payload is not None:
        _exclusive_bytes(raw, payload)
        raw_record = {
            "path": str(raw),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    valid = outcome.startswith("COMPLETE_VALID_CDX_CANARY")
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": outcome,
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "target_availability_plan_id": release["target_record"]["availability_plan_id"],
        "network_request_count": request_count[0],
        "stopped_on_http_429": outcome == "INCOMPLETE_HTTP_429_ARCHIVE_PROVIDER_CIRCUIT_OPEN",
        "response_diagnostics": diagnostics,
        "raw_response": raw_record,
        "error": error_text,
        "enumeration": parsed,
        "decision": {
            "bulk_cdx_release_may_be_prepared": valid,
            "archive_provider_branch_closed": outcome == "INCOMPLETE_HTTP_429_ARCHIVE_PROVIDER_CIRCUIT_OPEN",
            "offline_reconciliation_required": outcome == "INCOMPLETE_INVALID_CONTENT_PRESERVED_OFFLINE_RECONCILIATION_REQUIRED",
            "automatic_cascade_allowed": False,
            "capture_authorized": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "archive_metadata_requests": request_count[0],
            "archived_page_download_operations": 0,
            "artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    _atomic_json(partial, report)
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
        not_before = datetime.fromisoformat(release["adaptive_gate"]["not_before"])
        remaining = max(0, round((not_before - datetime.now(timezone.utc).astimezone()).total_seconds()))
        print(json.dumps({
            "valid": True,
            "release_id": release["release_id"],
            "target_rows": 1,
            "seconds_until_not_before": remaining,
            "maximum_network_requests": 1,
            "authoritative_executor": EXECUTOR,
            "descriptive_user_agent": USER_AGENT,
            "archived_page_download_allowed": False,
        }, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in (
        "report_id", "status", "network_request_count", "stopped_on_http_429"
    )}, indent=2))
    return 0 if report["error"] is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
