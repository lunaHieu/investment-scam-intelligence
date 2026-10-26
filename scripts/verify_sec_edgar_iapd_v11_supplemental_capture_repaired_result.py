"""Independently verify the metadata-limited V11 repaired result offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from scripts.repair_sec_edgar_iapd_v11_supplemental_capture_result import REPAIR_REPORT_ID, REPAIR_STATUS


QA_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_REPAIRED_RESULT_INDEPENDENT_QA_V1"
QA_STATUS = "PASS_REPAIRED_RAW_BYTES_METADATA_INCOMPLETE_EXTRACTION_CLOSED"


def verify(release_path: Path, report_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    report = load_object(report_path)
    errors: list[str] = []
    if report.get("report_id") != REPAIR_REPORT_ID:
        errors.append("unexpected repaired report identity")
    if report.get("status") != REPAIR_STATUS:
        errors.append("repaired report is not metadata-limited status")
    if report.get("network_operations") != 0:
        errors.append("repair verifier performed or claimed network operations")
    plan_path = Path(str(release["inputs"]["capture_plan"]["path"]))
    plan = load_object(plan_path)
    planned = list(plan.get("results", []))
    rows = list(report.get("rows", []))
    if len(rows) != len(planned) or report.get("planned_capture_count") != len(planned):
        errors.append("repaired result population differs from frozen plan")
    for index, source in enumerate(planned):
        if index >= len(rows):
            break
        row = rows[index]
        for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "snapshot_timestamp", "requested_archive_url", "capture_path"):
            if row.get(key) != source.get(key):
                errors.append(f"identity mismatch at row {index}: {key}")
        target = Path(str(source.get("capture_path", "")))
        if not target.is_file():
            errors.append(f"raw file missing at row {index}")
            continue
        if row.get("raw_bytes") != target.stat().st_size or row.get("raw_sha256") != sha256_file(target):
            errors.append(f"raw byte/hash mismatch at row {index}")
        if row.get("response_metadata_status") != "NOT_PERSISTED_BY_EXECUTOR":
            errors.append(f"metadata limitation missing at row {index}")
        if any(row.get(key) is not None for key in ("http_status", "content_type", "final_archive_url", "redirect_count", "attempt_count")):
            errors.append(f"repair fabricated HTTP metadata at row {index}")
    result = {
        "verification_id": QA_ID,
        "status": QA_STATUS if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "report_sha256": sha256_file(report_path), "plan_sha256": release["inputs"]["capture_plan"]["sha256"]},
        "checks": {"ordered_identity_preserved": not any("identity mismatch" in error or "population" in error for error in errors), "raw_byte_hashes_verified": not any("raw byte/hash" in error or "raw file" in error for error in errors), "metadata_fabrication_detected": any("fabricated HTTP" in error for error in errors), "network_operations": 0},
        "decision": {"capture_result_qa_passed": False, "text_extraction_release_may_be_prepared": False, "grouping_allowed": False, "labeling_allowed": False, "validation_or_test_opening_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "reservation_overwritten": False, "labels_created": 0, "model_operations": 0},
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite repaired-result QA")
    result = verify(args.release, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
