"""Build an offline, metadata-limited repair report for the V11 capture.

The executor's pre-network reservation and raw files are immutable.  This tool
does not recapture or overwrite them.  It materializes a separate report whose
only positive claim is that the frozen plan identities and local raw-byte
hashes reconcile; HTTP headers, redirects, and per-request evidence remain
explicitly unavailable.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


REPAIR_REPORT_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_CAPTURE_REPAIRED_RESULT_V1"
REPAIR_STATUS = "RECONCILED_CAPTURED_BYTES_METADATA_INCOMPLETE"
RECONCILIATION_STATUS = "PASS_RAW_BYTES_IDENTITY_RECONCILIATION_CAPTURE_METADATA_INCOMPLETE"


def build_repair(
    release_path: Path,
    release_qa_path: Path,
    reservation_path: Path,
    reconciliation_path: Path,
    output_path: Path,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite supplemental repaired result")
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    reservation = load_object(reservation_path)
    reconciliation = load_object(reconciliation_path)
    plan_path = Path(str(release["inputs"]["capture_plan"]["path"]))
    plan = load_object(plan_path)
    errors: list[str] = []
    if reservation.get("status") != "RESERVED_BEFORE_NETWORK_NON_RESUMABLE":
        errors.append("preserved reservation status is not expected")
    if reconciliation.get("status") != RECONCILIATION_STATUS:
        errors.append("raw-byte reconciliation is not a passing metadata-limited reconciliation")
    if reconciliation.get("decision", {}).get("capture_result_qa_passed") is not False:
        errors.append("reconciliation must not claim capture QA passed")
    if reconciliation.get("inputs", {}).get("release_sha256") != sha256_file(release_path):
        errors.append("reconciliation release hash is stale")
    if reconciliation.get("inputs", {}).get("release_qa_sha256") != sha256_file(release_qa_path):
        errors.append("reconciliation release-QA hash is stale")

    plan_rows = list(plan.get("results", []))
    reconciliation_rows = list(reconciliation.get("rows", []))
    if len(plan_rows) != len(reconciliation_rows):
        errors.append("reconciliation row count differs from frozen plan")
    repaired_rows: list[dict[str, Any]] = []
    for index, source in enumerate(plan_rows):
        if index >= len(reconciliation_rows):
            errors.append(f"missing reconciliation row {index}")
            continue
        evidence = reconciliation_rows[index]
        identity = {
            key: source[key]
            for key in (
                "availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url",
                "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path",
            )
        }
        for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "snapshot_timestamp", "requested_archive_url", "capture_path"):
            if evidence.get(key) != source.get(key):
                errors.append(f"identity mismatch at row {index}: {key}")
        target = Path(str(source["capture_path"]))
        if not target.is_file():
            errors.append(f"raw file missing at row {index}")
            raw_bytes = None
            raw_sha256 = None
        else:
            raw_bytes = target.stat().st_size
            raw_sha256 = sha256_file(target)
            if evidence.get("bytes") != raw_bytes or evidence.get("sha256") != raw_sha256:
                errors.append(f"raw byte/hash mismatch at row {index}")
        repaired_rows.append({
            **identity,
            "outcome": "CAPTURED_BYTES_RECONCILED",
            "raw_bytes": raw_bytes,
            "raw_sha256": raw_sha256,
            "response_metadata_status": "NOT_PERSISTED_BY_EXECUTOR",
            "http_status": None,
            "content_type": None,
            "final_archive_url": None,
            "redirect_count": None,
            "attempt_count": None,
            "diagnostics": {},
            "error": None,
        })

    result: dict[str, Any] = {
        "report_id": REPAIR_REPORT_ID,
        "created_at": (created_at or datetime.now(timezone.utc).astimezone()).isoformat(),
        "status": REPAIR_STATUS if not errors else "FAIL",
        "source_executor_report_id": release["planned_output"]["report_id"],
        "repair_reason": "Executor reported completion but left the pre-network reservation in the planned report path.",
        "inputs": {
            "release_path": str(release_path.resolve()),
            "release_sha256": sha256_file(release_path),
            "release_qa_path": str(release_qa_path.resolve()),
            "release_qa_sha256": sha256_file(release_qa_path),
            "reservation_path": str(reservation_path.resolve()),
            "reservation_sha256": sha256_file(reservation_path),
            "reconciliation_path": str(reconciliation_path.resolve()),
            "reconciliation_sha256": sha256_file(reconciliation_path),
            "capture_plan_path": str(plan_path.resolve()),
            "capture_plan_sha256": release["inputs"]["capture_plan"]["sha256"],
        },
        "planned_capture_count": len(plan_rows),
        "reconciled_capture_count": sum(row["outcome"] == "CAPTURED_BYTES_RECONCILED" for row in repaired_rows),
        "network_operations": 0,
        "rows": repaired_rows,
        "metadata_limitations": [
            "Response headers, redirect count, and per-request HTTP evidence were not persisted by the executor.",
            "This repaired report is not a passing capture QA and cannot open exact-text extraction.",
        ],
        "decision": {
            "capture_result_qa_passed": False,
            "text_extraction_release_may_be_prepared": False,
            "grouping_allowed": False,
            "labeling_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
            "recapture_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "raw_files_modified": 0,
            "reservation_overwritten": False,
            "candidate_live_domain_access_operations": 0,
            "labels_created": 0,
            "model_operations": 0,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_repair(args.release, args.release_qa, args.reservation, args.reconciliation, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == REPAIR_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
