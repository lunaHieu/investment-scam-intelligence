"""Verify a future concrete execution release for availability V11."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_availability_v11_protocol_v1 import (
    EXPECTED_IDS,
    PASS_STATUS as PROTOCOL_PASS,
    verify as verify_protocol,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RELEASE_V11"
PASS_STATUS = "PASS_FROZEN_EXACT_TWO_HOLDOUT_ROWS_LATEST_REQUEST_BOUND_RELEASE_V11"


def _aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp lacks timezone")
    return parsed


def _same_instant(left: datetime, right: datetime) -> bool:
    return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)


def _network_count(report: dict[str, Any]) -> int:
    for field in ("network_request_count", "network_request_count_this_attempt"):
        value = report.get(field)
        if isinstance(value, int):
            return value
    return 0


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
    except Exception as error:
        return {
            "verification_id": "ISI_SEC_EDGAR_IAPD_AVAILABILITY_RELEASE_QA_V11",
            "status": "FAIL",
            "errors": [f"Release loading failed: {type(error).__name__}: {error}"],
        }
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected V11 release identity")
    if release.get("status") != "FROZEN_EXACT_TWO_HOLDOUT_ROWS_NOT_BEFORE_GATE":
        errors.append("Unexpected V11 release status")
    for item in release.get("basis", []):
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"V11 release basis mismatch: {item['path']}")
    for role, item in release.get("inputs", {}).items():
        path = Path(item["path"]) if item.get("absolute", False) else root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"V11 release input mismatch: {role}")

    protocol_path = root / release["inputs"]["protocol"]["path"]
    protocol_qa_path = Path(release["inputs"]["protocol_qa"]["path"])
    latest_path = Path(release["inputs"]["latest_actual_archive_request_report"]["path"])
    protocol = load_object(protocol_path)
    protocol_qa = load_object(protocol_qa_path)
    latest = load_object(latest_path)
    protocol_check = verify_protocol(protocol_path)
    if protocol_check["errors"]:
        errors.append("Frozen V11 protocol no longer verifies")
    if protocol_qa.get("status") != PROTOCOL_PASS or protocol_qa.get("errors") != []:
        errors.append("V11 protocol QA is not PASS")
    if protocol_qa.get("protocol", {}).get("sha256") != sha256_file(protocol_path):
        errors.append("V11 protocol QA hash binding changed")
    if release.get("ordered_retry_rows") != protocol.get("ordered_retry_rows"):
        errors.append("V11 release retry rows differ from the frozen protocol")
    if [row.get("availability_plan_id") for row in release.get("ordered_retry_rows", [])] != EXPECTED_IDS:
        errors.append("V11 release identity/order changed")

    cooldown = release.get("cooldown_contract", {})
    try:
        latest_created = _aware(str(latest["created_at"]))
        declared_latest = _aware(str(cooldown["latest_actual_archive_request_created_at"]))
        not_before = _aware(str(cooldown["not_before"]))
        release_created = _aware(str(release["created_at"]))
        minimum = int(cooldown["minimum_cooldown_seconds"])
        if _network_count(latest) < 1:
            errors.append("V11 latest archive report has no real network request")
        if not _same_instant(latest_created, declared_latest):
            errors.append("V11 cooldown is not bound to the latest report created_at")
        if minimum < 86400 or not_before < latest_created + timedelta(seconds=minimum):
            errors.append("V11 not_before is shorter than the required cooldown")
        if release_created < latest_created or release_created >= not_before:
            errors.append("V11 release was not frozen inside the offline window")
        floor = _aware(protocol["future_release_contract"]["absolute_not_before_floor"])
        if not_before < floor:
            errors.append("V11 not_before predates the protocol floor")
    except Exception as error:
        minimum = None
        errors.append(f"V11 cooldown validation failed: {type(error).__name__}: {error}")

    if release.get("network_contract") != protocol.get("network_contract"):
        errors.append("V11 release network contract differs from the frozen protocol")
    planned = release.get("planned_output", {})
    expected_output = Path(protocol["future_release_contract"]["planned_output_path"])
    output = Path(planned.get("path", ""))
    if output != expected_output:
        errors.append("V11 planned output path changed")
    if planned.get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V11":
        errors.append("V11 planned report identity changed")
    if require_output_absent and (
        output.exists() or output.with_suffix(output.suffix + ".partial").exists()
    ):
        errors.append("V11 final or partial output already exists")
    decision = release.get("decision", {})
    if decision.get("exact_two_row_availability_execution_allowed_after_not_before") is not True:
        errors.append("V11 post-gate execution is not authorized")
    for field in (
        "candidate_live_domain_access_allowed",
        "archived_page_download_allowed",
        "capture_plan_mutation_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "model_scoring_allowed",
        "training_allowed",
    ):
        if decision.get(field) is not False:
            errors.append(f"Forbidden V11 release decision opened: {field}")

    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_AVAILABILITY_RELEASE_QA_V11",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {
            "ordered_retry_ids": [row.get("availability_plan_id") for row in release.get("ordered_retry_rows", [])],
            "latest_archive_request_report_sha256": sha256_file(latest_path),
            "minimum_cooldown_seconds": minimum,
            "not_before": cooldown.get("not_before"),
            "network_execution_allowed_at_release_time": False,
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.release)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite V11 release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
