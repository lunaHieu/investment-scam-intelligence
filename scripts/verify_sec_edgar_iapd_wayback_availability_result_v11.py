"""Independently verify a future exact-two-row availability V11 result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v4 import canonical, parse_time
from scripts.verify_sec_edgar_iapd_wayback_availability_v11_protocol_v1 import EXPECTED_IDS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


EXECUTOR = "scripts.retry_sec_edgar_iapd_wayback_availability_v11"


def _valid_snapshot_url(value: str, timestamp: str) -> bool:
    # Local implementation avoids depending on the historical V1 verifier API.
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname == "web.archive.org"
        and parsed.path.startswith(f"/web/{timestamp}/")
    )


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
        release_qa = load_object(release_qa_path)
        report = load_object(report_path)
        root = release_path.resolve().parents[1]
        protocol = load_object(root / release["inputs"]["protocol"]["path"])
        parent = load_object(Path(protocol["inputs"]["availability_report_v10"]["path"]))
    except Exception as error:
        return {
            "verification_id": "ISI_SEC_EDGAR_IAPD_AVAILABILITY_RESULT_QA_V11",
            "status": "FAIL",
            "errors": [f"Input loading failed: {type(error).__name__}: {error}"],
        }
    release_hash = sha256_file(release_path)
    release_qa_hash = sha256_file(release_qa_path)
    report_hash = sha256_file(report_path)
    if report.get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V11":
        errors.append("Unexpected V11 report identity")
    if report.get("executor") != EXECUTOR:
        errors.append("Unexpected V11 executor identity")
    if report.get("release_sha256") != release_hash or report.get("release_qa_sha256") != release_qa_hash:
        errors.append("V11 release/QA binding mismatch")
    if release_qa.get("release", {}).get("sha256") != release_hash or release_qa.get("errors") != []:
        errors.append("V11 release QA is not authoritative PASS")
    if report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("V11 final report still has a partial journal")
    try:
        if parse_time(str(report.get("created_at"))) < parse_time(release["cooldown_contract"]["not_before"]):
            errors.append("V11 result predates the frozen not_before")
    except Exception:
        errors.append("V11 result timestamp is invalid")

    parent_rows = parent.get("results", [])
    current_rows = report.get("results", [])
    parent_ids = [row.get("availability_plan_id") for row in parent_rows]
    current_ids = [row.get("availability_plan_id") for row in current_rows]
    if len(current_rows) != 115 or current_ids != parent_ids or len(set(current_ids)) != 115:
        errors.append("V11 membership/order changed")
    parent_by_id = {row["availability_plan_id"]: row for row in parent_rows}
    current_by_id = {row["availability_plan_id"]: row for row in current_rows}
    for identifier, row in parent_by_id.items():
        if row.get("error") is None and identifier in current_by_id:
            if canonical(row) != canonical(current_by_id[identifier]):
                errors.append(f"Resolved V10 result changed: {identifier}")
    retried = [str(value) for value in report.get("retried_availability_plan_ids", [])]
    if retried != EXPECTED_IDS[: len(retried)] or len(retried) != len(set(retried)):
        errors.append("V11 retry identity/order changed")
    attempts = report.get("logical_retry_attempt_count")
    requests = report.get("network_request_count_this_attempt")
    if attempts != len(retried):
        errors.append("V11 logical attempt count changed")
    maximum_redirects = int(release["network_contract"]["maximum_redirects"])
    if (
        not isinstance(requests, int)
        or requests < len(retried)
        or requests > len(retried) * (1 + maximum_redirects)
    ):
        errors.append("V11 HTTP request count is outside the redirect bound")
    if report.get("stopped_on_http_429") is not True and retried != EXPECTED_IDS:
        errors.append("V11 stopped early without HTTP 429")

    available = unavailable = unresolved = 0
    for row in current_rows:
        identifier = row.get("availability_plan_id")
        if row.get("error") is not None:
            unresolved += 1
            if row.get("available") is not None:
                errors.append(f"Unresolved V11 row has availability: {identifier}")
            if identifier in EXPECTED_IDS and row.get("queried") is True:
                diagnostics = row.get("response_diagnostics")
                if not isinstance(diagnostics, dict):
                    errors.append(f"Queried V11 error lacks diagnostics: {identifier}")
        elif row.get("available") is True:
            available += 1
            if row.get("snapshot_http_status") != "200" or not _valid_snapshot_url(
                str(row.get("snapshot_url") or ""), str(row.get("snapshot_timestamp") or "")
            ):
                errors.append(f"Invalid available V11 row: {identifier}")
        elif row.get("available") is False:
            unavailable += 1
            if any(row.get(field) is not None for field in ("snapshot_timestamp", "snapshot_url", "snapshot_http_status")):
                errors.append(f"Unavailable V11 row retains snapshot evidence: {identifier}")
        else:
            errors.append(f"Resolved V11 row lacks availability: {identifier}")
    for field, value in (
        ("available_snapshot_count", available),
        ("unavailable_snapshot_count", unavailable),
        ("unresolved_error_count", unresolved),
        ("requested_candidate_count", 115),
        ("resolved_results_reused_from_v10", 113),
        ("retry_candidate_count", 2),
    ):
        if report.get(field) != value:
            errors.append(f"V11 aggregate mismatch: {field}")
    if report.get("cumulative_network_request_count") != parent.get("cumulative_network_request_count") + requests:
        errors.append("V11 cumulative request count mismatch")
    has_429 = any("429" in str(row.get("error")) for row in current_rows)
    if bool(report.get("stopped_on_http_429")) != has_429:
        errors.append("V11 HTTP 429 flag and evidence disagree")
    complete = unresolved == 0
    if report.get("supplemental_availability_complete") is not complete:
        errors.append("V11 supplemental completeness flag changed")
    if report.get("status") != ("COMPLETE" if complete else "INCOMPLETE_ERRORS_PRESERVED"):
        errors.append("V11 report status does not match unresolved count")
    if report.get("original_capture_plan_mutation_allowed") is not False:
        errors.append("V11 result allows mutation of the completed capture plan")
    safety = report.get("safety_contract", {})
    for field in (
        "candidate_live_domain_access_operations",
        "archived_page_download_operations",
        "artifact_captures",
        "labels_created",
        "model_operations",
    ):
        if safety.get(field) != 0:
            errors.append(f"V11 safety count changed: {field}")
    if safety.get("training_allowed") is not False:
        errors.append("V11 result opened training")

    if errors:
        status = "FAIL"
    elif complete:
        status = "PASS_COMPLETE_SUPPLEMENTAL_AVAILABILITY_RESULT_CAPTURE_PLAN_UNCHANGED"
    else:
        status = "PASS_PARTIAL_ERRORS_PRESERVED_QUARANTINE_REMAINS"
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_AVAILABILITY_RESULT_QA_V11",
        "status": status,
        "inputs": {
            "release_sha256": release_hash,
            "release_qa_sha256": release_qa_hash,
            "report_sha256": report_hash,
            "parent_v10_sha256": sha256_file(Path(protocol["inputs"]["availability_report_v10"]["path"])),
        },
        "checks": {
            "membership_and_order_preserved": not any("membership/order" in error for error in errors),
            "resolved_v10_results_preserved": not any("Resolved V10" in error for error in errors),
            "retried_only_exact_two_rows": set(retried).issubset(set(EXPECTED_IDS)),
            "resolved_results": available + unavailable,
            "available_results": available,
            "unavailable_results": unavailable,
            "unresolved_results": unresolved,
            "logical_retry_attempts_v11": attempts,
            "network_requests_v11": requests,
            "stopped_on_http_429": report.get("stopped_on_http_429"),
        },
        "decision": {
            "supplemental_availability_complete": complete and not errors,
            "original_capture_plan_may_be_mutated": False,
            "newly_available_rows_require_separate_supplemental_capture_plan": True,
            "labeling_allowed": False,
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
        raise FileExistsError("Refusing to overwrite V11 result QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
