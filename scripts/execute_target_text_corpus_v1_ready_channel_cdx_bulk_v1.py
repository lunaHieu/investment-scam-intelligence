"""Execute the separately frozen exact-68 unresolved-only CDX metadata release."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1 import (
    CanaryHttpError,
    CanaryRateLimitStop,
    _atomic_json,
    _exclusive_bytes,
    build_request_url,
    fetch_cdx,
    parse_metadata,
)
from scripts.verify_target_text_corpus_v1_ready_channel_cdx_bulk_release_v1 import PASS_STATUS, target_rows, verify
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXECUTOR = "scripts.execute_target_text_corpus_v1_ready_channel_cdx_bulk_v1"


def _row_release(release: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(release)
    value["target_record"] = row
    value["cdx_contract"]["query"] = {"url": row["candidate_host"] + "/", **value["cdx_contract"].pop("query_template")}
    return value


def validate_inputs(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    release = load_object(release_path)
    qa = load_object(release_qa_path)
    checked = verify(release_path, require_output_absent=False)
    if checked.get("status") != PASS_STATUS or checked.get("errors"):
        raise PermissionError("Bulk CDX release recomputation failed")
    if qa.get("status") != PASS_STATUS or qa.get("errors") != [] or qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise PermissionError("Bulk CDX release QA is not authoritative PASS")
    return release, target_rows(release_path)


def execute(
    release_path: Path,
    release_qa_path: Path,
    now: datetime | None = None,
    *,
    fetcher: Callable = fetch_cdx,
    output_override: Path | None = None,
    raw_dir_override: Path | None = None,
) -> dict[str, Any]:
    release, rows = validate_inputs(release_path, release_qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    not_before = datetime.fromisoformat(release["execution_gate"]["not_before"])
    if current.tzinfo is None or current < not_before:
        raise PermissionError("Bulk CDX execution gate is closed")
    output = output_override or Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    raw_dir = raw_dir_override or Path(release["planned_output"]["raw_response_directory"])
    if output.exists() or partial.exists() or raw_dir.exists():
        raise FileExistsError("Refusing to run: bulk CDX final, partial or raw output exists")
    reservation = {"journal_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_BULK_JOURNAL_V1", "status": "PARTIAL_DO_NOT_AUTO_RESUME", "started_at": current.isoformat(), "release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "target_rows": 68, "network_request_count": 0, "results": [], "resume_allowed": False}
    _exclusive_bytes(partial, (json.dumps(reservation, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    raw_dir.mkdir(parents=True, exist_ok=False)
    request_count = [0]
    results: list[dict[str, Any]] = []
    stopped = False
    stop_reason = None
    for row in rows:
        row_release = _row_release(release, row)
        payload = None
        diagnostics: dict[str, Any] = {}
        parsed = None
        error_text = None
        outcome = "COMPLETE_VALID_CDX_METADATA"
        try:
            payload, diagnostics = fetcher(build_request_url(row_release["cdx_contract"]), row_release["cdx_contract"], request_count)
            parsed = parse_metadata(payload, row_release)
        except CanaryRateLimitStop as error:
            payload, diagnostics = error.payload, error.diagnostics
            error_text = f"{type(error).__name__}: {error}"
            outcome, stopped, stop_reason = "HTTP_429_PRESERVED", True, "HTTP_429"
        except CanaryHttpError as error:
            payload, diagnostics = error.payload, error.diagnostics
            error_text = f"{type(error).__name__}: {error}"
            outcome, stopped, stop_reason = "HTTP_OR_TRANSPORT_ERROR_PRESERVED", True, "HTTP_OR_TRANSPORT_ERROR"
        except Exception as error:
            error_text = f"{type(error).__name__}: {error}"
            outcome, stopped, stop_reason = "INVALID_OR_OTHER_ERROR_PRESERVED", True, "INVALID_OR_OTHER_ERROR"
        raw_record = None
        if payload is not None:
            raw_path = raw_dir / f"{row['availability_plan_id']}.bin"
            _exclusive_bytes(raw_path, payload)
            raw_record = {"path": str(raw_path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        results.append({"availability_plan_id": row["availability_plan_id"], "candidate_id": row["candidate_id"], "cohort": row["cohort"], "channel_id": row["channel_id"], "candidate_host": row["candidate_host"], "outcome": outcome, "response_diagnostics": diagnostics, "raw_response": raw_record, "enumeration": parsed, "error": error_text})
        _atomic_json(partial, {**reservation, "network_request_count": request_count[0], "results": results})
        if stopped:
            break
    attempted = {row["availability_plan_id"] for row in results}
    unresolved = [row["availability_plan_id"] for row in rows if row["availability_plan_id"] not in attempted]
    complete = not stopped and len(results) == 68
    report = {"report_id": release["planned_output"]["report_id"], "created_at": datetime.now(timezone.utc).astimezone().isoformat(), "status": "COMPLETE_EXACT_68_CDX_METADATA" if complete else "INCOMPLETE_ERROR_PRESERVED", "executor": EXECUTOR, "release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "target_rows": 68, "logical_attempt_count": len(results), "network_request_count": request_count[0], "stopped": stopped, "stop_reason": stop_reason, "unattempted_availability_plan_ids": unresolved, "results": results, "decision": {"capture_plan_may_be_prepared": complete, "automatic_retry_allowed": False, "capture_authorized": False, "labeling_allowed": False, "training_allowed": False}, "safety_contract": {"candidate_live_domain_access_operations": 0, "archive_metadata_requests": request_count[0], "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}}
    _atomic_json(partial, report)
    os.replace(partial, output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release, rows = validate_inputs(args.release, args.release_qa)
    if args.verify_only:
        remaining = max(0, round((datetime.fromisoformat(release["execution_gate"]["not_before"]) - datetime.now(timezone.utc).astimezone()).total_seconds()))
        print(json.dumps({"valid": True, "release_id": release["release_id"], "target_rows": len(rows), "seconds_until_not_before": remaining, "maximum_network_requests": 68, "archived_page_download_allowed": False}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "network_request_count", "stop_reason")}, indent=2))
    return 0 if report["status"] == "COMPLETE_EXACT_68_CDX_METADATA" else 2


if __name__ == "__main__":
    raise SystemExit(main())
