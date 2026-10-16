"""Independently verify a SEC/IAPD exact-missing-row capture retry release."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_wayback_capture_retry_release_v1 import (
    IDENTITY_KEYS,
    EXPECTED_PARTIAL_QA_DECISION,
    EXPECTED_PARTIAL_QA_SAFETY,
    PARTIAL_QA_ID,
    PARTIAL_QA_STATUS,
    RELEASE_ID,
    RETRY_OUTCOMES,
    SOURCE_RELEASE_ID,
    SOURCE_RELEASE_QA_STATUS,
    parse_time,
)
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url
from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import (
    verify as verify_source_capture_result,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in IDENTITY_KEYS}


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected capture retry release identity")
    inputs = release.get("inputs", {})
    qa_item = inputs.get("independent_partial_capture_qa", {})
    qa_path = Path(str(qa_item.get("path", "")))
    try:
        if sha256_file(qa_path) != qa_item.get("sha256"):
            errors.append("Independent partial capture QA hash mismatch")
        qa = load_object(qa_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        qa = {}
        errors.append(f"Cannot read independent partial capture QA: {error}")
    if qa.get("status") != PARTIAL_QA_STATUS:
        errors.append("Independent capture QA is not a passing partial result")
    if qa.get("verification_id") != PARTIAL_QA_ID:
        errors.append("Unexpected independent capture QA identity")
    if qa.get("errors") != []:
        errors.append("Independent capture QA contains errors")
    if qa.get("decision") != EXPECTED_PARTIAL_QA_DECISION:
        errors.append("Independent capture QA decisions do not match a passing partial result")
    if qa.get("safety_contract") != EXPECTED_PARTIAL_QA_SAFETY:
        errors.append("Independent capture QA safety contract changed")

    artifacts: dict[str, tuple[Path, str]] = {}
    for role in (
        "source_capture_release",
        "source_capture_release_qa",
        "capture_plan",
        "capture_report",
    ):
        item = inputs.get(role, {})
        path = Path(str(item.get("path", "")))
        expected_hash = str(item.get("sha256", ""))
        if (
            not path.is_absolute()
            or not path.is_file()
            or len(expected_hash) != 64
            or sha256_file(path) != expected_hash
        ):
            errors.append(f"Artifact binding mismatch: {role}")
        else:
            artifacts[role] = (path, expected_hash)
    if not all(role in artifacts for role in (
        "source_capture_release",
        "source_capture_release_qa",
        "capture_plan",
        "capture_report",
    )):
        source_release, source_release_qa, plan, report = {}, {}, {}, {}
    else:
        source_release = load_object(artifacts["source_capture_release"][0])
        source_release_qa = load_object(artifacts["source_capture_release_qa"][0])
        plan = load_object(artifacts["capture_plan"][0])
        report = load_object(artifacts["capture_report"][0])
    source_release_hash = artifacts.get("source_capture_release", (Path(), ""))[1]
    source_release_qa_hash = artifacts.get("source_capture_release_qa", (Path(), ""))[1]
    plan_hash = artifacts.get("capture_plan", (Path(), ""))[1]
    capture_report_hash = artifacts.get("capture_report", (Path(), ""))[1]
    if all(role in artifacts for role in (
        "source_capture_release",
        "source_capture_release_qa",
        "capture_report",
    )):
        recomputed_qa = verify_source_capture_result(
            artifacts["source_capture_release"][0],
            artifacts["source_capture_release_qa"][0],
            artifacts["capture_report"][0],
        )
        if qa != recomputed_qa:
            errors.append("Independent capture QA does not equal a full recomputation")
    if source_release.get("release_id") != SOURCE_RELEASE_ID:
        errors.append("Unexpected source capture release identity")
    if source_release_qa.get("status") != SOURCE_RELEASE_QA_STATUS:
        errors.append("Source capture release QA did not pass")
    if source_release_qa.get("release", {}).get("sha256") != source_release_hash:
        errors.append("Source capture release QA hash mismatch")
    source_plan = source_release.get("inputs", {}).get("capture_plan", {})
    if (
        source_plan.get("path") != str(artifacts.get("capture_plan", (Path(), ""))[0])
        or source_plan.get("sha256") != plan_hash
    ):
        errors.append("Source release capture-plan binding mismatch")
    expected_qa_inputs = {
        "release_sha256": source_release_hash,
        "release_qa_sha256": source_release_qa_hash,
        "report_sha256": capture_report_hash,
        "plan_sha256": plan_hash,
    }
    if qa.get("inputs") != expected_qa_inputs:
        errors.append("Independent capture QA input hashes do not match release artifacts")
    if report.get("report_id") != source_release.get("planned_output", {}).get("report_id"):
        errors.append("Capture report identity does not match source release")
    if report.get("release", {}).get("sha256") != source_release_hash:
        errors.append("Capture report source-release hash mismatch")
    if report.get("release_qa", {}).get("sha256") != source_release_qa_hash:
        errors.append("Capture report source-release-QA hash mismatch")
    if report.get("plan") != source_plan:
        errors.append("Capture report plan binding mismatch")

    plan_rows = list(plan.get("results", []))
    report_rows = list(report.get("results", []))
    if report.get("status") != "INCOMPLETE_FAILURES_PRESERVED":
        errors.append("Source capture report is not incomplete")
    if not plan_rows or len(plan_rows) != len(report_rows):
        errors.append("Capture plan/report populations differ or are empty")
    if source_plan.get("record_count") != len(plan_rows):
        errors.append("Source release plan count disagrees with the plan")

    expected_completed: list[dict[str, Any]] = []
    expected_retry: list[dict[str, Any]] = []
    for index, source in enumerate(plan_rows):
        if index >= len(report_rows):
            break
        row = report_rows[index]
        if _identity(row) != _identity(source):
            errors.append(f"Capture plan/report identity mismatch at row {index}")
            continue
        try:
            assert_archive_url(str(row["requested_archive_url"]))
            if "id_/" not in str(row["requested_archive_url"]):
                errors.append(f"Raw replay modifier missing at row {index}")
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid archive URL at row {index}: {error}")
        target = Path(str(row.get("capture_path", "")))
        if row.get("outcome") == "CAPTURED":
            if not target.is_file():
                errors.append(f"Completed capture missing at row {index}")
                continue
            observed_bytes = target.stat().st_size
            observed_hash = sha256_file(target)
            if row.get("bytes") != observed_bytes or row.get("sha256") != observed_hash:
                errors.append(f"Completed capture byte/hash mismatch at row {index}")
                continue
            if (
                row.get("http_status") != 200
                or not str(row.get("content_type") or "").casefold().startswith("text/html")
                or row.get("error") is not None
            ):
                errors.append(f"Completed capture metadata invalid at row {index}")
                continue
            expected_completed.append(
                {**_identity(row), "bytes": observed_bytes, "sha256": observed_hash}
            )
        elif row.get("outcome") in RETRY_OUTCOMES:
            if target.exists():
                errors.append(f"Retry target already exists at row {index}")
            if (
                not row.get("error")
                or row.get("bytes") is not None
                or row.get("sha256") is not None
            ):
                errors.append(f"Retry row does not preserve a clean error at row {index}")
            expected_retry.append(
                {
                    **_identity(row),
                    "prior_outcome": row.get("outcome"),
                    "prior_http_status": row.get("http_status"),
                    "prior_error": row.get("error"),
                }
            )
        else:
            errors.append(f"Unsupported source outcome at row {index}")

    expected_counts = {
        "planned_capture_count": len(plan_rows),
        "captured_count": len(expected_completed),
        "failed_count": sum(row.get("outcome") == "FAILED" for row in report_rows),
        "not_attempted_count": sum(
            row.get("outcome") == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP"
            for row in report_rows
        ),
    }
    qa_checks = qa.get("checks", {})
    for key, expected in expected_counts.items():
        if report.get(key) != expected or qa_checks.get(key) != expected:
            errors.append(f"Partial QA/report aggregate mismatch: {key}")
    captured_by_cohort = dict(
        Counter(
            str(row.get("cohort"))
            for row in report_rows
            if row.get("outcome") == "CAPTURED"
        )
    )
    if report.get("captured_by_cohort") != captured_by_cohort or qa_checks.get("captured_by_cohort") != captured_by_cohort:
        errors.append("Partial QA/report captured-by-cohort aggregate mismatch")
    requests = report.get("network_request_count", -1)
    if requests < expected_counts["captured_count"] + expected_counts["failed_count"] or requests > len(plan_rows) * 4:
        errors.append("Capture network request count is outside the source bound")
    stopped_on_429 = any(row.get("http_status") == 429 for row in report_rows)
    if report.get("stopped_on_http_429") is not stopped_on_429 or qa_checks.get("stopped_on_http_429") is not stopped_on_429:
        errors.append("HTTP 429 stop flag and source evidence disagree")

    if release.get("completed_capture_ledger") != expected_completed:
        errors.append("Completed capture ledger changed")
    if release.get("retry_rows") != expected_retry:
        errors.append("Retry population/order changed")
    if release.get("source_population_count") != len(plan_rows):
        errors.append("Source population count changed")
    if release.get("completed_capture_count") != len(expected_completed):
        errors.append("Completed capture count changed")
    if release.get("retry_capture_count") != len(expected_retry) or not expected_retry:
        errors.append("Retry capture count is invalid")

    try:
        report_created_at = parse_time(str(report["created_at"]))
        release_created_at = parse_time(str(release["created_at"]))
        not_before = parse_time(str(release.get("execution_contract", {}).get("not_before")))
        if not_before < report_created_at + timedelta(hours=24):
            errors.append("Retry cooldown is less than 24 hours")
        if not_before < release_created_at:
            errors.append("Retry not-before predates release creation")
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"Invalid retry timestamp: {error}")

    contract = release.get("execution_contract", {})
    expected_contract = {
        "minimum_cooldown_seconds_after_partial_report": 86400.0,
        "allowed_network_hosts": ["web.archive.org"],
        "minimum_delay_seconds": 30.0,
        "maximum_attempts_per_snapshot": 1,
        "timeout_seconds": 30,
        "maximum_redirects": 3,
        "maximum_response_bytes": 26214400,
        "required_content_type_prefix": "text/html",
        "https_only": True,
        "raw_replay_modifier_required": True,
        "automatic_external_redirect_following": False,
        "stop_on_http_429": True,
        "errors_are_preserved": True,
        "completed_rows_are_immutable": True,
        "failed_rows_are_not_replaced": True,
        "output_overwrite_allowed": False,
    }
    for key, expected in expected_contract.items():
        if contract.get(key) != expected:
            errors.append(f"Retry execution contract changed: {key}")
    output_path = Path(str(release.get("planned_output", {}).get("path", "")))
    source_report_path = artifacts.get("capture_report", (Path(), ""))[0]
    if not output_path.is_absolute() or output_path == source_report_path:
        errors.append("Retry report path is invalid or overwrites the source report")
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        errors.append("Retry report target or partial already exists")
    if release.get("planned_output", {}).get("report_id") != "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_MISSING_ROW_RETRY_REPORT_V1":
        errors.append("Unexpected retry report identity")

    decision = release.get("decision", {})
    if decision.get("archive_only_missing_row_retry_allowed_at_or_after_not_before") is not True:
        errors.append("Archive-only retry gate is not declared")
    for gate in (
        "candidate_live_domain_access_allowed",
        "text_extraction_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "training_allowed",
        "model_scoring_allowed",
    ):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden retry gate opened: {gate}")

    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_CAPTURE_MISSING_ROW_RETRY_RELEASE_INDEPENDENT_QA_V1",
        "status": "PASS_EXACT_MISSING_ROWS_ARCHIVE_ONLY_RETRY_RELEASE" if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {
            "source_population_count": len(plan_rows),
            "completed_capture_count": len(expected_completed),
            "retry_capture_count": len(expected_retry),
            "completed_bytes_and_hashes_preserved": not any("Completed capture" in error for error in errors),
            "retry_population_and_order_preserved": "Retry population/order changed" not in errors,
            "minimum_cooldown_seconds": contract.get("minimum_cooldown_seconds_after_partial_report"),
            "maximum_attempts_per_snapshot": contract.get("maximum_attempts_per_snapshot"),
            "archive_host_only": contract.get("allowed_network_hosts") == ["web.archive.org"],
            "stop_on_http_429": contract.get("stop_on_http_429"),
        },
        "decision": {
            "release_qa_passed": not errors,
            "execution_allowed_at_or_after_not_before": not errors,
            "candidate_live_domain_access_allowed": False,
            "text_extraction_allowed": False,
            "labeling_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
            "model_scoring_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "captures": 0,
            "raw_files_modified": 0,
            "labels": 0,
            "model": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.release)
    if args.output:
        if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
            raise FileExistsError("Refusing to overwrite capture retry release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".partial")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
