"""Post-execution verifier for the one-row SEC/IAPD capture retry.

Unlike V1, this verifier does not call the pre-execution release verifier after
the report exists. It independently validates immutable release/QA bindings,
the completed-capture ledger, the final report, and any raw retry bytes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_MISSING_ROW_RETRY_RELEASE_V1"
RELEASE_STATUS = "FROZEN_EXACT_MISSING_ROWS_ARCHIVE_ONLY_RETRY_NOT_BEFORE_GATE"
QA_STATUS = "PASS_EXACT_MISSING_ROWS_ARCHIVE_ONLY_RETRY_RELEASE"
EXECUTOR = "scripts.execute_sec_edgar_iapd_wayback_capture_retry_v2"


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
        qa = load_object(release_qa_path)
        report = load_object(report_path)
    except Exception as error:
        return {
            "verification_id": "ISI_SEC_EDGAR_IAPD_CAPTURE_RETRY_RESULT_QA_V2",
            "status": "FAIL",
            "errors": [f"Input loading failed: {type(error).__name__}: {error}"],
        }

    if release.get("release_id") != RELEASE_ID or release.get("status") != RELEASE_STATUS:
        errors.append("Unexpected frozen retry release identity or status")
    release_hash = sha256_file(release_path)
    qa_hash = sha256_file(release_qa_path)
    report_hash = sha256_file(report_path)
    if qa.get("status") != QA_STATUS or qa.get("errors") != []:
        errors.append("Frozen release QA is not PASS")
    if qa.get("release", {}).get("sha256") != release_hash:
        errors.append("Frozen release QA binding mismatch")
    if Path(release.get("planned_output", {}).get("path", "")) != report_path:
        errors.append("Report is not the frozen planned output")
    if report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Final report still has a partial journal")
    if report.get("release_sha256") != release_hash or report.get("release_qa_sha256") != qa_hash:
        errors.append("Retry report input binding mismatch")
    if report.get("executor") != EXECUTOR:
        errors.append("Retry report was not produced by the V2 executor")

    completed_ok = True
    for completed in release.get("completed_capture_ledger", []):
        path = Path(completed["capture_path"])
        if (
            not path.is_file()
            or path.stat().st_size != completed.get("bytes")
            or sha256_file(path) != completed.get("sha256")
        ):
            completed_ok = False
            errors.append(f"Completed capture changed: {completed.get('availability_plan_id')}")
            break

    results = report.get("results", [])
    if (
        len(release.get("retry_rows", [])) != 1
        or len(results) != 1
        or results[0].get("availability_plan_id")
        != release.get("retry_rows", [{}])[0].get("availability_plan_id")
    ):
        errors.append("Retry result population changed")
        row: dict[str, Any] = {}
    else:
        row = results[0]

    raw_verified = False
    diagnostics_preserved = False
    if row:
        raw = Path(row["capture_path"])
        if row.get("outcome") == "CAPTURED":
            raw_verified = (
                raw.is_file()
                and raw.stat().st_size == row.get("bytes")
                and sha256_file(raw) == row.get("sha256")
                and int(row.get("bytes", 0)) >= 1024
            )
            if not raw_verified:
                errors.append("Captured retry raw byte/hash validation failed")
        elif row.get("outcome") == "FAILED":
            if raw.exists():
                errors.append("Failed retry wrote a raw capture")
            diagnostics = row.get("response_diagnostics", {})
            diagnostics_preserved = (
                isinstance(diagnostics.get("response_sha256"), str)
                and len(diagnostics["response_sha256"]) == 64
                and isinstance(diagnostics.get("response_bytes"), int)
                and isinstance(diagnostics.get("response_headers"), dict)
            )
            if not diagnostics_preserved:
                errors.append("Failed retry lacks complete response diagnostics")
        else:
            errors.append("Unexpected retry outcome")

    captured = (
        report.get("status") == "COMPLETE"
        and report.get("captured_count") == 1
        and report.get("failed_count") == 0
        and raw_verified
        and not errors
    )
    failed_preserved = (
        report.get("status") == "INCOMPLETE_FAILURE_PRESERVED"
        and report.get("captured_count") == 0
        and report.get("failed_count") == 1
        and diagnostics_preserved
        and not errors
    )
    if not captured and not failed_preserved and not errors:
        errors.append("Retry report summary is inconsistent with its row outcome")

    if errors:
        status = "FAIL"
    elif captured:
        status = "PASS_COMPLETE_SUPPLEMENTAL_PIPELINE_MAY_BE_PREPARED"
    else:
        status = "PASS_RETRY_FAILURE_PRESERVED_QUARANTINE_REMAINS"

    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_CAPTURE_RETRY_RESULT_QA_V2",
        "status": status,
        "inputs": {
            "release_sha256": release_hash,
            "release_qa_sha256": qa_hash,
            "report_sha256": report_hash,
        },
        "checks": {
            "retry_rows": len(results),
            "completed_capture_ledger_preserved": completed_ok,
            "captured_count": report.get("captured_count"),
            "failed_count": report.get("failed_count"),
            "raw_byte_hash_verified": raw_verified,
            "diagnostics_preserved": diagnostics_preserved,
            "http_status": row.get("http_status") if row else None,
            "response_bytes": row.get("response_diagnostics", {}).get("response_bytes") if row else None,
            "response_sha256": row.get("response_diagnostics", {}).get("response_sha256") if row else None,
        },
        "decision": {
            "supplemental_pipeline_may_be_prepared": captured,
            "quarantine_remains": failed_preserved,
            "another_retry_allowed_by_this_qa": False,
            "original_review_population_may_be_mutated": False,
            "training_allowed": False,
            "model_scoring_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "raw_files_modified": 0,
            "labels": 0,
            "model": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite capture retry QA V2")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
