"""Verify a completed one-row alternate-snapshot CDX enumeration report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1 import (
    EXECUTOR,
    parse_and_select,
)
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1 import (
    PASS_STATUS,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


def verify(
    release_path: Path,
    release_qa_path: Path,
    report_path: Path,
    *,
    require_frozen_output_path: bool = True,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
        qa = load_object(release_qa_path)
        report = load_object(report_path)
    except Exception as error:
        return {
            "verification_id": "ISI_SEC_EDGAR_IAPD_ALTERNATE_SNAPSHOT_CDX_RESULT_QA_V1",
            "status": "FAIL",
            "errors": [f"Input loading failed: {type(error).__name__}: {error}"],
        }
    release_check = verify_release(release_path, require_output_absent=False)
    if release_check["errors"]:
        errors.append("Frozen CDX release no longer verifies")
    release_hash = sha256_file(release_path)
    qa_hash = sha256_file(release_qa_path)
    report_hash = sha256_file(report_path)
    if qa.get("status") != PASS_STATUS or qa.get("errors") != []:
        errors.append("Frozen CDX release QA is not PASS")
    if qa.get("release", {}).get("sha256") != release_hash:
        errors.append("Frozen CDX release QA binding mismatch")
    if require_frozen_output_path and Path(release["planned_output"]["path"]) != report_path:
        errors.append("CDX report is not the frozen planned output")
    if report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Final CDX report still has a partial journal")
    if report.get("executor") != EXECUTOR:
        errors.append("CDX report executor changed")
    if report.get("release_sha256") != release_hash or report.get("release_qa_sha256") != qa_hash:
        errors.append("CDX report input binding mismatch")
    if report.get("target_availability_plan_id") != release["target_record"]["availability_plan_id"]:
        errors.append("CDX result target identity changed")
    if report.get("failed_snapshot_timestamp_excluded") != release["target_record"]["failed_snapshot_timestamp"]:
        errors.append("CDX result did not preserve the failed timestamp exclusion")
    if report.get("network_request_count") != 1:
        errors.append("CDX result did not use exactly one network request")

    enumeration = report.get("enumeration")
    selected = enumeration.get("selected_candidate") if isinstance(enumeration, dict) else None
    selected_valid = False
    no_candidate = False
    failure_preserved = False
    if report.get("status") == "COMPLETE_ALTERNATE_CANDIDATE_SELECTED_CAPTURE_NOT_AUTHORIZED":
        if report.get("error") is not None or not isinstance(enumeration, dict):
            errors.append("Selected-candidate report has an error or lacks enumeration")
        else:
            rows = [release["cdx_contract"]["query"]["fields"]] + enumeration.get("eligible_rows", [])
            # Reconstruct the table in frozen field order and recompute selection.
            table = [rows[0]] + [
                [row[field] for field in rows[0]] for row in enumeration.get("eligible_rows", [])
            ]
            recomputed = parse_and_select(json.dumps(table).encode("utf-8"), release)
            selected_valid = recomputed["selected_candidate"] == selected
            if not selected_valid:
                errors.append("Selected CDX candidate is not independently reproducible")
    elif report.get("status") == "COMPLETE_NO_ELIGIBLE_ALTERNATE_QUARANTINE_REMAINS":
        no_candidate = (
            report.get("error") is None
            and isinstance(enumeration, dict)
            and enumeration.get("eligible_row_count") == 0
            and selected is None
        )
        if not no_candidate:
            errors.append("No-alternate report is internally inconsistent")
    elif report.get("status") == "INCOMPLETE_ERROR_PRESERVED":
        diagnostics = report.get("response_diagnostics", {})
        failure_preserved = (
            isinstance(report.get("error"), str)
            and report.get("enumeration") is None
            and isinstance(diagnostics, dict)
        )
        if not failure_preserved:
            errors.append("CDX error result is not preserved consistently")
    else:
        errors.append("Unexpected CDX report status")

    decision = report.get("decision", {})
    if decision.get("alternate_capture_is_authorized") is not False:
        errors.append("CDX result improperly authorizes capture")
    if decision.get("same_failed_timestamp_may_be_used") is not False:
        errors.append("CDX result reopened the failed timestamp")
    if decision.get("original_review_population_may_be_mutated") is not False:
        errors.append("CDX result permits mutation of the frozen review population")
    if decision.get("training_allowed") is not False:
        errors.append("CDX result opened training")

    if errors:
        status = "FAIL"
    elif selected_valid:
        status = "PASS_ALTERNATE_CANDIDATE_SELECTED_SEPARATE_CAPTURE_RELEASE_MAY_BE_PREPARED"
    elif no_candidate:
        status = "PASS_NO_ALTERNATE_SNAPSHOT_QUARANTINE_REMAINS"
    else:
        status = "PASS_CDX_FAILURE_PRESERVED_QUARANTINE_REMAINS"
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_ALTERNATE_SNAPSHOT_CDX_RESULT_QA_V1",
        "status": status,
        "inputs": {
            "release_sha256": release_hash,
            "release_qa_sha256": qa_hash,
            "report_sha256": report_hash,
        },
        "checks": {
            "target_rows": 1,
            "network_request_count": report.get("network_request_count"),
            "failed_timestamp_excluded": report.get("failed_snapshot_timestamp_excluded"),
            "selected_candidate_recomputed": selected_valid,
            "no_eligible_alternate": no_candidate,
            "failure_diagnostics_preserved": failure_preserved,
            "archived_page_downloads": 0,
        },
        "decision": {
            "separate_capture_release_may_be_prepared": selected_valid,
            "capture_authorized_by_this_qa": False,
            "quarantine_remains": not selected_valid,
            "original_review_population_may_be_mutated": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "archived_page_downloads": 0,
            "captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
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
        raise FileExistsError("Refusing to overwrite alternate-snapshot CDX result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
