"""Verify an A1 CDX report produced under the explicit timing-only owner override."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1 import EXECUTOR
from scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_v1 import parse_and_select
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1 import PASS_STATUS, verify as verify_override
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(
    override_path: Path,
    override_qa_path: Path,
    report_path: Path,
    *,
    require_frozen_output_path: bool = True,
) -> dict[str, Any]:
    errors: list[str] = []
    override = load_object(override_path)
    override_qa = load_object(override_qa_path)
    report = load_object(report_path)
    checked = verify_override(override_path, require_output_absent=False)
    if checked.get("errors"):
        errors.append("Owner timing override no longer verifies")
    if override_qa.get("status") != PASS_STATUS or override_qa.get("errors") != [] or override_qa.get("override", {}).get("sha256") != sha256_file(override_path):
        errors.append("Owner timing override QA is not authoritative PASS")
    release_path = Path(override["inputs"]["frozen_release"]["path"])
    release_qa_path = Path(override["inputs"]["frozen_release_qa"]["path"])
    release = load_object(release_path)
    if require_frozen_output_path and Path(release["planned_output"]["path"]) != report_path:
        errors.append("Owner-override CDX report is not at the original frozen output path")
    if report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("Final owner-override CDX report still has a partial journal")
    if report.get("executor") != EXECUTOR:
        errors.append("Owner-override CDX executor identity changed")
    if report.get("release_sha256") != sha256_file(release_path) or report.get("release_qa_sha256") != sha256_file(release_qa_path) or report.get("owner_timing_override_sha256") != sha256_file(override_path):
        errors.append("Owner-override CDX input hash binding mismatch")
    timing = report.get("timing_override", {})
    try:
        started = datetime.fromisoformat(report["started_at"])
        created = datetime.fromisoformat(report["created_at"])
        effective = datetime.fromisoformat(override["timing_override"]["effective_not_before"])
        original = datetime.fromisoformat(override["timing_override"]["original_not_before"])
        if started < effective or created < started or started >= original:
            errors.append("Report timestamps do not prove authorized early execution")
    except Exception as exc:
        errors.append(f"Invalid report timing evidence: {type(exc).__name__}: {exc}")
    if timing != {
        "explicit_owner_authorization": True,
        "original_not_before": override["timing_override"]["original_not_before"],
        "effective_not_before": override["timing_override"]["effective_not_before"],
        "scope": "NOT_BEFORE_ONLY",
    }:
        errors.append("Report timing override evidence changed")
    if report.get("target_availability_plan_id") != release["target_record"]["availability_plan_id"] or report.get("failed_snapshot_timestamp_excluded") != release["target_record"]["failed_snapshot_timestamp"]:
        errors.append("Owner-override CDX target/exclusion identity changed")
    if report.get("network_request_count") != 1:
        errors.append("Owner-override CDX did not use exactly one request")

    enumeration = report.get("enumeration")
    selected = enumeration.get("selected_candidate") if isinstance(enumeration, dict) else None
    selected_valid = False
    no_candidate = False
    failure_preserved = False
    if report.get("status") == "COMPLETE_ALTERNATE_CANDIDATE_SELECTED_CAPTURE_NOT_AUTHORIZED":
        if report.get("error") is not None or not isinstance(enumeration, dict):
            errors.append("Selected-candidate report has an error or lacks enumeration")
        else:
            fields = release["cdx_contract"]["query"]["fields"]
            table = [fields] + [[row[field] for field in fields] for row in enumeration.get("eligible_rows", [])]
            selected_valid = parse_and_select(json.dumps(table).encode("utf-8"), release)["selected_candidate"] == selected
            if not selected_valid:
                errors.append("Selected CDX candidate is not independently reproducible")
    elif report.get("status") == "COMPLETE_NO_ELIGIBLE_ALTERNATE_QUARANTINE_REMAINS":
        no_candidate = report.get("error") is None and isinstance(enumeration, dict) and enumeration.get("eligible_row_count") == 0 and selected is None
        if not no_candidate:
            errors.append("No-alternate report is internally inconsistent")
    elif report.get("status") == "INCOMPLETE_ERROR_PRESERVED":
        failure_preserved = isinstance(report.get("error"), str) and report.get("enumeration") is None and isinstance(report.get("response_diagnostics"), dict)
        if not failure_preserved:
            errors.append("CDX error result is not preserved consistently")
    else:
        errors.append("Unexpected owner-override CDX report status")
    decision = report.get("decision", {})
    for key in ("alternate_capture_is_authorized", "same_failed_timestamp_may_be_used", "original_review_population_may_be_mutated", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"Owner-override CDX report opened forbidden decision: {key}")
    safety = report.get("safety_contract", {})
    if safety.get("candidate_live_domain_access_operations") != 0 or safety.get("archived_page_download_operations") != 0 or safety.get("labels_created") != 0 or safety.get("model_operations") != 0:
        errors.append("Owner-override CDX safety counters changed")

    if errors:
        status = "FAIL"
    elif selected_valid:
        status = "PASS_OWNER_OVERRIDE_ALTERNATE_CANDIDATE_SELECTED_SEPARATE_CAPTURE_RELEASE_MAY_BE_PREPARED"
    elif no_candidate:
        status = "PASS_OWNER_OVERRIDE_NO_ALTERNATE_SNAPSHOT_QUARANTINE_REMAINS"
    else:
        status = "PASS_OWNER_OVERRIDE_CDX_FAILURE_PRESERVED_QUARANTINE_REMAINS"
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_ALTERNATE_SNAPSHOT_CDX_OWNER_OVERRIDE_RESULT_QA_V1",
        "status": status,
        "inputs": {"override_sha256": sha256_file(override_path), "override_qa_sha256": sha256_file(override_qa_path), "report_sha256": sha256_file(report_path)},
        "checks": {"target_rows": 1, "network_request_count": report.get("network_request_count"), "explicit_early_owner_override_verified": not errors, "selected_candidate_recomputed": selected_valid, "no_eligible_alternate": no_candidate, "failure_diagnostics_preserved": failure_preserved, "archived_page_downloads": 0},
        "decision": {"separate_capture_release_may_be_prepared": selected_valid, "capture_authorized_by_this_qa": False, "quarantine_remains": not selected_valid, "original_review_population_may_be_mutated": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--override", type=Path, required=True)
    parser.add_argument("--override-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite owner-override CDX result QA")
    result = verify(args.override, args.override_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
