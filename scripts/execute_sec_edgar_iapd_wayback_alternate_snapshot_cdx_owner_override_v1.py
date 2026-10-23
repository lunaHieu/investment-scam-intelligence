"""Execute the one-request CDX release under an explicit owner timing-only override."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1 import (
    CdxRateLimitStop,
    CdxResponseError,
    _atomic_checkpoint,
    _exclusive_create,
    build_request_url,
    fetch_cdx,
    parse_and_select,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXECUTOR = "scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1"
OVERRIDE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_ALTERNATE_SNAPSHOT_CDX_OWNER_TIMING_OVERRIDE_V1"


def validate_inputs(override_path: Path, override_qa_path: Path, *, require_output_absent: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1 import verify

    override = load_object(override_path)
    qa = load_object(override_qa_path)
    checked = verify(override_path, require_output_absent=require_output_absent)
    if checked.get("errors"):
        raise PermissionError("Owner timing override independent recomputation failed")
    if qa.get("status") != checked.get("status") or qa.get("errors") != []:
        raise PermissionError("Owner timing override QA is not authoritative PASS")
    if qa.get("override", {}).get("sha256") != sha256_file(override_path):
        raise PermissionError("Owner timing override QA hash binding changed")
    release = load_object(Path(override["inputs"]["frozen_release"]["path"]))
    return override, release


def execute(
    override_path: Path,
    override_qa_path: Path,
    now: datetime | None = None,
    *,
    fetcher: Callable[[str, dict[str, Any], list[int]], tuple[bytes, dict[str, Any]]] = fetch_cdx,
    output_override: Path | None = None,
) -> dict[str, Any]:
    override, release = validate_inputs(override_path, override_qa_path, require_output_absent=output_override is None)
    current = now or datetime.now(timezone.utc).astimezone()
    effective_not_before = datetime.fromisoformat(override["timing_override"]["effective_not_before"])
    if current.tzinfo is None or current < effective_not_before:
        raise PermissionError("Owner timing override is not yet effective")
    output = output_override or Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("Refusing to run: CDX final or partial output already exists")

    override_hash = sha256_file(override_path)
    release_path = Path(override["inputs"]["frozen_release"]["path"])
    release_qa_path = Path(override["inputs"]["frozen_release_qa"]["path"])
    started_at = current.isoformat()
    reservation = {
        "journal_id": "ISI_SEC_EDGAR_IAPD_ALTERNATE_SNAPSHOT_CDX_OWNER_OVERRIDE_JOURNAL_V1",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "started_at": started_at,
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "owner_timing_override_sha256": override_hash,
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
        "started_at": started_at,
        "status": status,
        "executor": EXECUTOR,
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "owner_timing_override_sha256": override_hash,
        "timing_override": {
            "explicit_owner_authorization": True,
            "original_not_before": override["timing_override"]["original_not_before"],
            "effective_not_before": override["timing_override"]["effective_not_before"],
            "scope": "NOT_BEFORE_ONLY",
        },
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
    parser.add_argument("--override", type=Path, required=True)
    parser.add_argument("--override-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        override, release = validate_inputs(args.override, args.override_qa, require_output_absent=True)
        now = datetime.now(timezone.utc).astimezone()
        effective = datetime.fromisoformat(override["timing_override"]["effective_not_before"])
        print(json.dumps({
            "status": "PASS_OWNER_TIMING_OVERRIDE_EXECUTION_PREFLIGHT",
            "effective_now": now >= effective,
            "maximum_logical_requests": release["cdx_contract"]["maximum_logical_requests"],
            "archived_page_download_allowed": False,
        }, indent=2))
        return 0 if now >= effective else 1
    report = execute(args.override, args.override_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "network_request_count", "stopped_on_http_429")}, indent=2))
    return 0 if report["error"] is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
