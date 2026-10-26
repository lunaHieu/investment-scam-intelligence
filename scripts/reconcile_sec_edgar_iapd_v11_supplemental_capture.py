"""Reconcile raw bytes after a V11 supplemental executor finalization failure.

This tool is deliberately offline-only.  It never contacts an archive host and
never overwrites the reservation/report produced by the capture executor.  The
output is an evidence inventory, not a capture-result replacement: response
headers and redirect metadata are not recoverable when the executor failed to
persist its final report, so text extraction remains closed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


RESERVATION_STATUS = "RESERVED_BEFORE_NETWORK_NON_RESUMABLE"
RECONCILIATION_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_RAW_BYTE_RECONCILIATION_V1"


def reconcile(
    release_path: Path,
    release_qa_path: Path,
    reservation_path: Path,
    output_path: Path,
    reconciled_at: datetime | None = None,
) -> dict[str, Any]:
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite raw-byte reconciliation")
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    reservation = load_object(reservation_path)
    plan_path = Path(str(release["inputs"]["capture_plan"]["path"]))
    plan = load_object(plan_path)
    errors: list[str] = []
    release_sha256 = sha256_file(release_path)
    release_qa_sha256 = sha256_file(release_qa_path)
    reservation_sha256 = sha256_file(reservation_path)
    if reservation.get("status") != RESERVATION_STATUS:
        errors.append("Reservation is not the preserved non-resumable pre-network record")
    if reservation.get("release_sha256") != release_sha256:
        errors.append("Reservation release hash does not match frozen release")
    if reservation.get("release_qa_sha256") != release_qa_sha256:
        errors.append("Reservation release-QA hash does not match frozen release QA")
    if reservation.get("planned_capture_count") != len(plan.get("results", [])):
        errors.append("Reservation planned count does not match frozen plan")

    rows: list[dict[str, Any]] = []
    for index, source in enumerate(plan.get("results", [])):
        target = Path(str(source["capture_path"]))
        row = {
            "index": index,
            "availability_plan_id": source["availability_plan_id"],
            "shortlist_id": source["shortlist_id"],
            "cohort": source["cohort"],
            "candidate_host": source["candidate_host"],
            "snapshot_timestamp": source["snapshot_timestamp"],
            "requested_archive_url": source["requested_archive_url"],
            "capture_path": str(target),
            "raw_file_exists": target.is_file(),
        }
        if target.is_file():
            row["bytes"] = target.stat().st_size
            row["sha256"] = sha256_file(target)
        else:
            row["bytes"] = None
            row["sha256"] = None
            errors.append(f"Raw capture file is missing at row {index}")
        rows.append(row)

    timestamp = (reconciled_at or datetime.now(timezone.utc).astimezone()).isoformat()
    result: dict[str, Any] = {
        "reconciliation_id": RECONCILIATION_ID,
        "created_at": timestamp,
        "status": "PASS_RAW_BYTES_IDENTITY_RECONCILIATION_CAPTURE_METADATA_INCOMPLETE" if not errors else "FAIL",
        "purpose": "Preserve independent evidence after executor report finalization failure without overwriting the reservation or recapturing.",
        "inputs": {
            "release_path": str(release_path.resolve()),
            "release_sha256": release_sha256,
            "release_qa_path": str(release_qa_path.resolve()),
            "release_qa_sha256": release_qa_sha256,
            "reservation_path": str(reservation_path.resolve()),
            "reservation_sha256": reservation_sha256,
            "capture_plan_path": str(plan_path.resolve()),
            "capture_plan_sha256": release["inputs"]["capture_plan"]["sha256"],
        },
        "checks": {
            "ordered_plan_identity_preserved": not errors,
            "raw_byte_files_present": not any("Raw capture file" in error for error in errors),
            "raw_byte_hashes_recorded": not any(row["sha256"] is None for row in rows),
            "network_operations": 0,
            "labels_created": 0,
            "model_operations": 0,
        },
        "rows": rows,
        "metadata_limitations": [
            "The executor reservation was preserved because its final report was not persisted.",
            "Response headers, redirect count, and per-request HTTP evidence are not recoverable from raw files alone.",
            "This reconciliation does not authorize exact-text extraction, grouping, labeling, validation/test opening, or training.",
        ],
        "decision": {
            "capture_result_qa_passed": False,
            "text_extraction_release_may_be_prepared": False,
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = reconcile(args.release, args.release_qa, args.reservation, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
