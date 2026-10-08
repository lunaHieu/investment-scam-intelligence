"""Independently audit Target Text Corpus V1 Wayback capture result V2."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url
from scripts.capture_target_text_corpus_v1_wayback_plan import EXPECTED_BY_CHANNEL, validate_plan
from scripts.query_target_text_corpus_v1_wayback_availability import load_json, sha256_file


EXPECTED_CAPTURED_BY_CHANNEL = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": 4,
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": 5,
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": 6,
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": 8,
}


def verify(*, plan_path: Path, v1_path: Path, v2_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    plan = validate_plan(plan_path, sha256_file(plan_path))
    v1 = load_json(v1_path)
    v2 = load_json(v2_path)
    if v1.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_REPORT_V1":
        errors.append("Unexpected capture report V1 ID")
    if v2.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_REPORT_V2":
        errors.append("Unexpected capture report V2 ID")
    if v2.get("plan_sha256") != sha256_file(plan_path):
        errors.append("V2 capture-plan hash mismatch")
    if v2.get("parent_report_sha256") != sha256_file(v1_path):
        errors.append("V2 parent-report hash mismatch")
    plan_by_id = {str(row["candidate_id"]): row for row in plan["results"]}
    v1_by_id = {str(row["candidate_id"]): row for row in v1.get("results", [])}
    v2_by_id = {str(row["candidate_id"]): row for row in v2.get("results", [])}
    if len(plan_by_id) != 29 or set(plan_by_id) != set(v1_by_id) or set(plan_by_id) != set(v2_by_id):
        errors.append("Plan/V1/V2 candidate membership changed")
    if v2.get("prior_captured_results_reused") != 0:
        errors.append("V2 unexpectedly claims a reused V1 capture")
    retry_ids = [str(value) for value in v2.get("retried_candidate_ids", [])]
    if len(retry_ids) != 29 or set(retry_ids) != set(plan_by_id):
        errors.append("V2 did not retry exactly all 29 unresolved plan rows")
    if v2.get("network_request_count_this_attempt") != 29:
        errors.append("V2 request count changed")
    if v2.get("cumulative_capture_network_request_count") != 30:
        errors.append("Cumulative capture request count changed")
    if v2.get("stopped_on_http_429") is not False or v2.get("not_attempted_count") != 0:
        errors.append("V2 unexpectedly stopped or left rows unattempted")

    captured_paths: set[Path] = set()
    capture_root = Path(str(plan["capture_root"])).resolve()
    for candidate_id, result in v2_by_id.items():
        planned = plan_by_id.get(candidate_id, {})
        for key in (
            "channel_id", "channel_target_stratum", "candidate_host", "candidate_url",
            "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path"
        ):
            if result.get(key) != planned.get(key):
                errors.append(f"Plan/result mismatch for {candidate_id}: {key}")
        target = Path(str(result.get("capture_path", ""))).resolve()
        if capture_root not in target.parents:
            errors.append(f"Capture target escaped root: {candidate_id}")
        if result.get("outcome") == "CAPTURED":
            captured_paths.add(target)
            if not target.is_file():
                errors.append(f"Captured file missing: {candidate_id}")
                continue
            actual_bytes = target.stat().st_size
            actual_hash = sha256_file(target)
            if actual_bytes != result.get("bytes") or actual_hash != result.get("sha256"):
                errors.append(f"Captured byte/hash mismatch: {candidate_id}")
            if actual_bytes < 1024:
                errors.append(f"Captured file below minimum size: {candidate_id}")
            if result.get("http_status") != 200:
                errors.append(f"Captured result lacks HTTP 200: {candidate_id}")
            if not str(result.get("content_type", "")).casefold().startswith("text/html"):
                errors.append(f"Captured result has non-HTML content type: {candidate_id}")
            try:
                assert_archive_url(str(result.get("final_archive_url") or ""))
            except ValueError as error:
                errors.append(f"Captured final URL invalid for {candidate_id}: {error}")
            if result.get("error") is not None:
                errors.append(f"Captured result retains error: {candidate_id}")
        elif result.get("outcome") == "FAILED":
            if target.exists():
                errors.append(f"Failed result unexpectedly wrote a file: {candidate_id}")
            if not str(result.get("error") or "").startswith("ValueError: Archived HTML capture is unexpectedly small:"):
                errors.append(f"Unexpected failure class: {candidate_id}")
            if any(result.get(key) is not None for key in (
                "final_archive_url", "redirect_count", "http_status", "content_type",
                "bytes", "sha256"
            )):
                errors.append(f"Failed result retains capture claims: {candidate_id}")
        else:
            errors.append(f"Unexpected V2 outcome: {candidate_id}")
    on_disk = {
        path.resolve()
        for path in capture_root.rglob("*")
        if path.is_file()
    } if capture_root.is_dir() else set()
    if on_disk != captured_paths:
        errors.append("Raw capture directory contains missing or unregistered files")

    captured_by_channel = Counter(
        str(row["channel_id"])
        for row in v2_by_id.values()
        if row.get("outcome") == "CAPTURED"
    )
    failed_by_channel = Counter(
        str(row["channel_id"])
        for row in v2_by_id.values()
        if row.get("outcome") == "FAILED"
    )
    if dict(captured_by_channel) != EXPECTED_CAPTURED_BY_CHANNEL:
        errors.append(f"Captured-by-channel counts changed: {dict(captured_by_channel)}")
    if sum(captured_by_channel.values()) != 23 or sum(failed_by_channel.values()) != 6:
        errors.append("V2 captured/failed aggregate counts changed")
    if Counter(captured_by_channel) + Counter(failed_by_channel) != Counter(EXPECTED_BY_CHANNEL):
        errors.append("Captured plus failed channel totals do not match the plan")
    expected_safety = {
        "candidate_live_domain_access_operations": 0,
        "only_web_archive_host_accessed": True,
        "raw_replay_modifier_used": True,
        "automatic_external_redirect_following": False,
        "labels_created": 0,
        "model_operations": 0,
        "training_allowed": False,
    }
    if v2.get("safety_contract") != expected_safety:
        errors.append("V2 capture safety contract changed")
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_INDEPENDENT_QA_V2",
        "status": "PASS_23_RAW_CAPTURES_6_SMALL_RESPONSES_PRESERVED" if not errors else "FAIL",
        "inputs": {
            "plan": {"path": str(plan_path), "sha256": sha256_file(plan_path)},
            "capture_v1": {"path": str(v1_path), "sha256": sha256_file(v1_path)},
            "capture_v2": {"path": str(v2_path), "sha256": sha256_file(v2_path)},
        },
        "checks": {
            "candidate_membership_preserved": set(plan_by_id) == set(v1_by_id) == set(v2_by_id),
            "all_plan_rows_attempted_in_v2": set(retry_ids) == set(plan_by_id),
            "raw_file_set_matches_report": on_disk == captured_paths,
            "raw_byte_and_hash_checks_passed": not any("byte/hash mismatch" in error for error in errors),
            "archive_final_url_checks_passed": not any("final URL invalid" in error for error in errors),
            "captured_count": len(captured_paths),
            "failed_small_response_count": sum(failed_by_channel.values()),
            "captured_by_channel": dict(captured_by_channel),
            "failed_by_channel": dict(failed_by_channel),
        },
        "decision": {
            "raw_capture_qa_passed": not errors,
            "exact_text_extraction_allowed_for_captured_rows": not errors,
            "failed_rows_may_be_silently_replaced": False,
            "live_candidate_domain_access_allowed": False,
            "binary_labeling_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "new_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--capture-v1", type=Path, required=True)
    parser.add_argument("--capture-v2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    result = verify(plan_path=args.plan, v1_path=args.capture_v1, v2_path=args.capture_v2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
