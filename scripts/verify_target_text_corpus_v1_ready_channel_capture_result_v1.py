"""Independently verify exact-53 ready-channel capture bytes and membership."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_release_v1 import PASS_STATUS, load, sha256_file


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict:
    errors: list[str] = []
    release, release_qa, report = load(release_path), load(release_qa_path), load(report_path)
    plan_path = Path(release["inputs"]["capture_plan"]["path"])
    plan = load(plan_path)
    if release_qa.get("status") != PASS_STATUS or release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("release QA binding mismatch")
    if report.get("release", {}).get("sha256") != sha256_file(release_path) or report.get("release_qa", {}).get("sha256") != sha256_file(release_qa_path):
        errors.append("report release binding mismatch")
    planned = {row["capture_plan_id"]: row for row in plan["results"]}
    results = {row["capture_plan_id"]: row for row in report.get("results", [])}
    if list(results) != list(planned) or len(results) != 53:
        errors.append("report membership/order differs from exact plan")
    captured_paths: set[Path] = set()
    for row_id, result in results.items():
        source = planned.get(row_id, {})
        for key in ("availability_plan_id", "candidate_id", "cohort", "channel_id", "candidate_host", "snapshot_timestamp", "snapshot_original_url", "snapshot_digest", "requested_archive_url", "capture_path"):
            if result.get(key) != source.get(key):
                errors.append(f"plan/result mismatch {row_id}: {key}")
        target = Path(str(result.get("capture_path", "")))
        if result.get("outcome") == "CAPTURED":
            captured_paths.add(target.resolve())
            if not target.is_file() or target.stat().st_size != result.get("bytes") or sha256_file(target) != result.get("sha256"):
                errors.append(f"captured byte/hash mismatch: {row_id}")
            if result.get("http_status") != 200 or not str(result.get("content_type", "")).casefold().startswith("text/html"):
                errors.append(f"invalid captured response: {row_id}")
        elif result.get("outcome") in {"FAILED", "NOT_ATTEMPTED_AFTER_ERROR_STOP"}:
            if target.exists():
                errors.append(f"non-captured target exists: {row_id}")
        else:
            errors.append(f"unknown outcome: {row_id}")
    complete = len(captured_paths) == 53 and report.get("status") == "COMPLETE"
    integrity_passed = not errors
    return {"verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_RESULT_QA_V1", "status": ("PASS_COMPLETE_53_RAW_CAPTURES_EXACT_TEXT_MAY_BE_PREPARED" if complete and integrity_passed else "PASS_PARTIAL_CAPTURE_PRESERVED_RETRY_RELEASE_REQUIRED" if integrity_passed else "FAIL"), "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "report_sha256": sha256_file(report_path), "plan_sha256": sha256_file(plan_path)}, "checks": {"planned_rows": 53, "captured_rows": len(captured_paths), "raw_byte_hashes_verified": integrity_passed, "complete": complete}, "decision": {"exact_text_release_may_be_prepared": complete and integrity_passed, "automatic_retry_allowed": False, "candidate_live_domain_access_allowed": False, "labeling_allowed": False, "training_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "captures": 0, "labels": 0, "model": 0}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
