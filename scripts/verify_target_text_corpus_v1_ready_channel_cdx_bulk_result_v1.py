"""Verify raw bytes and membership for the exact-68 ready-channel CDX result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.execute_target_text_corpus_v1_ready_channel_cdx_bulk_v1 import _row_release
from scripts.execute_target_text_corpus_v1_ready_channel_cdx_canary_v1 import parse_metadata
from scripts.verify_target_text_corpus_v1_ready_channel_cdx_bulk_release_v1 import target_rows
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict:
    errors: list[str] = []
    release, qa, report = load_object(release_path), load_object(release_qa_path), load_object(report_path)
    rows = target_rows(release_path)
    if report.get("release_sha256") != sha256_file(release_path) or report.get("release_qa_sha256") != sha256_file(release_qa_path):
        errors.append("Bulk result release hash binding changed")
    results = report.get("results", [])
    expected_prefix = [row["availability_plan_id"] for row in rows[:len(results)]]
    if [row.get("availability_plan_id") for row in results] != expected_prefix:
        errors.append("Bulk result membership/order changed")
    by_id = {row["availability_plan_id"]: row for row in rows}
    for result in results:
        raw = result.get("raw_response")
        if raw is None:
            continue
        path = Path(raw["path"])
        if not path.is_file():
            errors.append(f"Raw response missing: {result['availability_plan_id']}")
            continue
        payload = path.read_bytes()
        if len(payload) != raw.get("bytes") or hashlib.sha256(payload).hexdigest() != raw.get("sha256"):
            errors.append(f"Raw response byte/hash mismatch: {result['availability_plan_id']}")
            continue
        if result.get("outcome") == "COMPLETE_VALID_CDX_METADATA":
            recomputed = parse_metadata(payload, _row_release(release, by_id[result["availability_plan_id"]]))
            if recomputed != result.get("enumeration"):
                errors.append(f"Metadata recomputation mismatch: {result['availability_plan_id']}")
    complete = report.get("status") == "COMPLETE_EXACT_68_CDX_METADATA" and len(results) == 68 and report.get("network_request_count") == 68
    status = "PASS_COMPLETE_EXACT_68_CDX_METADATA_CAPTURE_PLAN_MAY_BE_PREPARED" if complete and not errors else ("PASS_PARTIAL_ERROR_PRESERVED_CAPTURE_PLAN_BLOCKED" if not errors else "FAIL")
    return {"verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_BULK_RESULT_QA_V1", "status": status, "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "report_sha256": sha256_file(report_path)}, "checks": {"target_rows": 68, "result_rows": len(results), "network_requests": report.get("network_request_count"), "raw_byte_hashes_verified": not errors, "complete": complete}, "decision": {"capture_plan_may_be_prepared": complete and not errors, "automatic_retry_allowed": False, "capture_authorized": False, "labeling_allowed": False, "training_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.release, args.release_qa, args.report)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite bulk result QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
