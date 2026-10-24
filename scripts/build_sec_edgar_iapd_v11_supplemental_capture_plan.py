"""Build an immutable, two-row supplemental SEC/IAPD Wayback capture plan.

This plan is deliberately separate from the frozen 58-row capture plan.  It is
metadata-only: no archive page is downloaded and no candidate domain is
contacted while building it.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url, raw_replay_url
from scripts.verify_sec_edgar_iapd_wayback_availability_result_v1 import read_jsonl
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


REPORT_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_PLAN_V1"
PLAN_STATUS = "FROZEN_EXACT_TWO_ROW_SUPPLEMENTAL_AVAILABLE_CAPTURE_PLAN_V1"
QA_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_PLAN_INDEPENDENT_QA_V1"
QA_STATUS = "PASS_EXACT_TWO_ROW_SUPPLEMENTAL_CAPTURE_PLAN"
AVAILABILITY_REPORT_ID = "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V11"
AVAILABILITY_QA_ID = "ISI_SEC_EDGAR_IAPD_AVAILABILITY_RESULT_QA_V11"
EXPECTED_IDS = (
    "TTCV1_EDGAR_AVAIL_HOLDOUT_011",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_018",
)
IDENTITY_FIELDS = (
    "availability_plan_id",
    "shortlist_id",
    "cohort",
    "candidate_host",
    "candidate_url",
)


def safe_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    if not sanitized or sanitized in {".", ".."}:
        raise ValueError(f"Unsafe path component: {value}")
    return sanitized


def _load_source(path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    if len(rows) != 115:
        raise ValueError(f"Expected 115 source rows, found {len(rows)}")
    return rows


def build_plan(
    *, source_plan_path: Path, availability_path: Path, availability_qa_path: Path,
    raw_root: Path, capture_date: str,
) -> dict[str, Any]:
    errors: list[str] = []
    source_rows = _load_source(source_plan_path)
    availability = load_object(availability_path)
    availability_qa = load_object(availability_qa_path)
    result_rows = list(availability.get("results", []))
    source_hash = sha256_file(source_plan_path)
    availability_hash = sha256_file(availability_path)
    availability_qa_hash = sha256_file(availability_qa_path)

    if availability.get("report_id") != AVAILABILITY_REPORT_ID:
        errors.append("Unexpected V11 availability report identity")
    if availability.get("status") != "COMPLETE":
        errors.append("V11 availability report is not complete")
    if len(result_rows) != 115 or availability.get("requested_candidate_count") != 115:
        errors.append("V11 availability result is not the complete 115-row population")
    if availability.get("unresolved_error_count") != 0:
        errors.append("V11 availability result still has unresolved rows")
    if availability_qa.get("verification_id") != AVAILABILITY_QA_ID:
        errors.append("Unexpected V11 independent availability QA identity")
    if availability_qa.get("status") != "PASS_COMPLETE_SUPPLEMENTAL_AVAILABILITY_RESULT_CAPTURE_PLAN_UNCHANGED":
        errors.append("V11 independent availability QA did not pass")
    if availability_qa.get("inputs", {}).get("report_sha256") != availability_hash:
        errors.append("V11 availability QA/result hash binding mismatch")
    if availability_qa.get("checks", {}).get("resolved_results") != 115:
        errors.append("V11 QA did not recompute 115 resolved rows")
    if availability_qa.get("checks", {}).get("retried_only_exact_two_rows") is not True:
        errors.append("V11 QA does not bind the exact two-row retry")

    if len(result_rows) == len(source_rows):
        for index, (source, observed) in enumerate(zip(source_rows, result_rows)):
            for field in IDENTITY_FIELDS:
                if observed.get(field) != source.get(field):
                    errors.append(f"Source/result identity mismatch at row {index}: {field}")
            if observed.get("query_timestamp") != source.get("target_timestamp"):
                errors.append(f"Source/result query timestamp mismatch at row {index}")

    source_by_id = {str(row.get("availability_plan_id")): row for row in source_rows}
    result_by_id = {str(row.get("availability_plan_id")): row for row in result_rows}
    expected_ids = list(EXPECTED_IDS)
    selected = []
    for plan_id in expected_ids:
        source = source_by_id.get(plan_id)
        observed = result_by_id.get(plan_id)
        if source is None or observed is None:
            errors.append(f"Missing exact V11 supplemental row: {plan_id}")
            continue
        if observed.get("available") is not True or observed.get("error") is not None:
            errors.append(f"V11 supplemental row is not available/resolved: {plan_id}")
            continue
        if observed.get("snapshot_http_status") != "200":
            errors.append(f"V11 supplemental row lacks HTTP 200 snapshot evidence: {plan_id}")
            continue
        if source.get("cohort") != "EXTERNAL_HOLDOUT":
            errors.append(f"V11 supplemental row changed cohort: {plan_id}")
            continue
        try:
            replay_url, timestamp = raw_replay_url(str(observed["snapshot_url"]))
            assert_archive_url(replay_url)
            host = safe_component(str(source["candidate_host"]).casefold().rstrip("."))
            cohort = safe_component(str(source["cohort"]))
            safe_id = safe_component(plan_id)
        except (KeyError, ValueError) as error:
            errors.append(f"Invalid V11 supplemental row {plan_id}: {error}")
            continue
        target_root = (
            raw_root.resolve()
            / "target_text_corpus_v1"
            / "sec_edgar_iapd_v11_supplemental_wayback_snapshots_v1"
        ).resolve()
        target = (target_root / cohort / f"{safe_id}__{host}.html").resolve()
        if target_root not in target.parents:
            errors.append(f"Capture target escaped supplemental root: {target}")
        selected.append({
            **source,
            "archived_page_downloaded": False,
            "artifact_captured": False,
            "plan_status": "PLANNED_NOT_EXECUTED_SUPPLEMENTAL",
            "training_eligible": "NO",
            "availability": {
                "available": True,
                "snapshot_timestamp": timestamp,
                "snapshot_url": observed["snapshot_url"],
                "snapshot_http_status": observed["snapshot_http_status"],
                "query_timestamp": observed["query_timestamp"],
                "report_row_sha256": observed.get("response_diagnostics", {}).get("response_sha256"),
            },
            "snapshot_timestamp": timestamp,
            "snapshot_url": observed["snapshot_url"],
            "requested_archive_url": replay_url,
            "capture_path": str(target),
        })

    if [str(row.get("availability_plan_id")) for row in selected] != expected_ids:
        errors.append("Supplemental plan membership/order is not the exact V11 two-row order")
    if len(selected) != 2:
        errors.append("Supplemental plan does not contain exactly two rows")
    if any(Path(str(row["capture_path"])).exists() for row in selected):
        errors.append("A supplemental immutable capture target already exists")
    if errors:
        raise ValueError(f"V11 supplemental capture-plan validation failed: {errors}")

    raw_root_resolved = raw_root.resolve()
    capture_root = (
        raw_root_resolved / "target_text_corpus_v1" /
        "sec_edgar_iapd_v11_supplemental_wayback_snapshots_v1"
    ).resolve()
    return {
        "report_id": REPORT_ID,
        "created_at": capture_date,
        "status": PLAN_STATUS,
        "tooling_version": "v11-supplemental-v1",
        "availability_generation": "v11",
        "source_candidate_count": 115,
        "planned_capture_count": 2,
        "planned_by_cohort": dict(Counter(str(row["cohort"]) for row in selected)),
        "source_plan": {"path": str(source_plan_path.resolve()), "sha256": source_hash, "record_count": 115},
        "availability_result": {
            "path": str(availability_path.resolve()), "sha256": availability_hash,
            "report_id": AVAILABILITY_REPORT_ID, "created_at": availability.get("created_at"),
        },
        "independent_availability_qa": {
            "path": str(availability_qa_path.resolve()), "sha256": availability_qa_hash,
            "verification_id": AVAILABILITY_QA_ID,
            "required_status": availability_qa.get("status"),
        },
        "raw_root": str(raw_root_resolved),
        "capture_root": str(capture_root),
        "ordered_supplemental_ids": expected_ids,
        "frozen_original_capture_plan_mutated": False,
        "results": selected,
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "archived_page_download_operations": 0,
            "candidate_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--availability", type=Path, required=True)
    parser.add_argument("--availability-qa", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite frozen V11 supplemental capture plan")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.capture_date):
        raise ValueError("capture-date must be YYYY-MM-DD")
    plan = build_plan(
        source_plan_path=args.source_plan,
        availability_path=args.availability,
        availability_qa_path=args.availability_qa,
        raw_root=args.raw_root,
        capture_date=args.capture_date,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({
        "status": plan["status"], "planned_capture_count": plan["planned_capture_count"],
        "output": str(args.output), "sha256": sha256_file(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
