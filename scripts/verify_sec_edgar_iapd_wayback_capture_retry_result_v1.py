"""Verify the one-row SEC/IAPD capture retry result and raw bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.execute_sec_edgar_iapd_wayback_capture_retry_v1 import validate_inputs
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path, release_qa_path: Path, report_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release, _ = validate_inputs(release_path, release_qa_path)
    except Exception as error:
        return {"verification_id": "ISI_SEC_EDGAR_IAPD_CAPTURE_RETRY_RESULT_QA_V1", "status": "FAIL", "errors": [f"Input validation failed: {type(error).__name__}: {error}"]}
    report = load_object(report_path)
    if report.get("release_sha256") != sha256_file(release_path) or report.get("release_qa_sha256") != sha256_file(release_qa_path):
        errors.append("Retry report input binding mismatch")
    results = report.get("results", [])
    if len(results) != 1 or results[0].get("availability_plan_id") != release["retry_rows"][0]["availability_plan_id"]:
        errors.append("Retry result population changed")
    else:
        row = results[0]
        raw = Path(row["capture_path"])
        if row.get("outcome") == "CAPTURED":
            if not raw.is_file() or raw.stat().st_size != row.get("bytes") or sha256_file(raw) != row.get("sha256") or int(row.get("bytes", 0)) < 1024:
                errors.append("Captured retry raw byte/hash validation failed")
        elif row.get("outcome") == "FAILED":
            if raw.exists():
                errors.append("Failed retry wrote a raw capture")
            if "unexpectedly small" in str(row.get("error", "")).casefold() and not row.get("response_diagnostics", {}).get("response_sha256"):
                errors.append("Below-minimum retry lacks response diagnostics")
        else:
            errors.append("Unexpected retry outcome")
    captured = report.get("captured_count") == 1 and not errors
    return {"verification_id": "ISI_SEC_EDGAR_IAPD_CAPTURE_RETRY_RESULT_QA_V1", "status": "PASS_COMPLETE_SUPPLEMENTAL_PIPELINE_MAY_BE_PREPARED" if captured else ("PASS_RETRY_FAILURE_PRESERVED_QUARANTINE_REMAINS" if not errors else "FAIL"), "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "report_sha256": sha256_file(report_path)}, "checks": {"retry_rows": len(results), "captured_count": report.get("captured_count"), "failed_count": report.get("failed_count"), "raw_byte_hash_verified": captured, "diagnostics_preserved": not errors}, "decision": {"supplemental_pipeline_may_be_prepared": captured, "original_review_population_may_be_mutated": False, "training_allowed": False, "model_scoring_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels": 0, "model": 0}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite capture retry QA")
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
