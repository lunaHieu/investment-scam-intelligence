"""Independently verify the decoupled crash-safe capture amendment."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.execute_sec_edgar_iapd_wayback_capture_v2 import (
    AUTHORITATIVE_MODULE,
    DIAGNOSTIC_HEADER_ALLOWLIST,
    validate_amendment,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


QA_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_EXECUTION_AMENDMENT_INDEPENDENT_QA_V1"
QA_STATUS = "PASS_DECOUPLED_CRASH_SAFE_CAPTURE_AMENDMENT"


def verify(amendment_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        amendment, release, plan, release_path, qa_path = validate_amendment(amendment_path)
    except Exception as error:
        amendment, release, plan = {}, {}, {}
        release_path = qa_path = Path(".")
        errors.append(f"Amendment validation failed: {type(error).__name__}: {error}")

    binding = amendment.get("execution_binding", {})
    rows = list(plan.get("results", []))
    cohort_counts = dict(Counter(str(row.get("cohort")) for row in rows))
    if len(rows) != binding.get("capture_plan_rows"):
        errors.append("Capture population or cohort composition changed")
    if binding.get("capture_plan_by_cohort") != cohort_counts:
        errors.append("Amendment cohort binding changed")
    if binding.get("authorized_executor_module") != AUTHORITATIVE_MODULE:
        errors.append("Authorized executor changed")
    if binding.get("allowlisted_http_diagnostic_headers") != list(DIAGNOSTIC_HEADER_ALLOWLIST):
        errors.append("Diagnostic header allowlist changed")
    for flag in (
        "reservation_before_first_request_required",
        "checkpoint_after_each_row_required",
        "original_v5_not_before_remains_binding",
    ):
        if binding.get(flag) is not True:
            errors.append(f"Required crash-safe binding is missing: {flag}")
    for flag in (
        "availability_v10_is_capture_prerequisite",
        "same_process_after_availability_429_allowed",
        "automatic_partial_resume_allowed",
    ):
        if binding.get(flag) is not False:
            errors.append(f"Forbidden coupling/resume binding is open: {flag}")
    if binding.get("availability_requests_in_capture_process") != 0:
        errors.append("Capture process permits availability requests")
    report_path = Path(str(release.get("planned_output", {}).get("path", "")))
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Capture output already exists")
    expected_output = amendment.get("independent_qa_output", {})
    if expected_output.get("verification_id") != QA_ID or expected_output.get("required_status") != QA_STATUS:
        errors.append("Independent QA output contract changed")

    return {
        "verification_id": QA_ID,
        "status": QA_STATUS if not errors else "FAIL",
        "amendment": {
            "path": str(amendment_path.resolve()),
            "sha256": sha256_file(amendment_path),
        },
        "inputs": {
            "capture_release_v5_sha256": sha256_file(release_path) if release_path.is_file() else None,
            "independent_release_qa_v5_sha256": sha256_file(qa_path) if qa_path.is_file() else None,
            "capture_plan_sha256": release.get("inputs", {}).get("capture_plan", {}).get("sha256"),
        },
        "checks": {
            "capture_plan_rows": len(rows),
            "capture_plan_by_cohort": cohort_counts,
            "availability_v10_is_capture_prerequisite": binding.get(
                "availability_v10_is_capture_prerequisite"
            ),
            "same_process_after_availability_429_allowed": binding.get(
                "same_process_after_availability_429_allowed"
            ),
            "reservation_before_first_request_required": binding.get(
                "reservation_before_first_request_required"
            ),
            "checkpoint_after_each_row_required": binding.get("checkpoint_after_each_row_required"),
            "automatic_partial_resume_allowed": binding.get("automatic_partial_resume_allowed"),
            "diagnostic_header_allowlist": binding.get("allowlisted_http_diagnostic_headers"),
            "planned_output_absent": not report_path.exists()
            and not report_path.with_suffix(report_path.suffix + ".partial").exists(),
        },
        "decision": {
            "capture_execution_allowed_under_amendment": not errors,
            "candidate_live_domain_access_allowed": False,
            "text_extraction_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "raw_files_modified": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite capture amendment QA")
    result = verify(args.amendment)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
