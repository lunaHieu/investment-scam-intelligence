"""Independently recompute the captured-subset admission view."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_sec_edgar_iapd_captured_subset_v1 import VIEW_ID, VIEW_STATUS, build
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


QA_ID = "ISI_SEC_EDGAR_IAPD_CAPTURED_SUBSET_INDEPENDENT_QA_V1"
QA_STATUS = "PASS_57_CAPTURED_SUBSET_EXACT_TEXT_RELEASE_MAY_BE_PREPARED"


def verify(release_path: Path, view_path: Path) -> dict:
    errors = []
    try:
        release = load_object(release_path)
        contract = release["population_contract"]
        actual = load_object(view_path)
        expected = build(release_path, require_outputs_absent=False)
    except Exception as error:
        actual, expected, contract = {}, {}, {}
        errors.append(f"Subset recomputation failed: {type(error).__name__}: {error}")
    if actual != expected:
        errors.append("Captured-subset view differs from full recomputation")
    if actual.get("report_id") != VIEW_ID or actual.get("status") != VIEW_STATUS:
        errors.append("Captured-subset identity or status changed")
    if actual.get("captured_count") != contract.get("admitted_captured_rows") or actual.get("quarantined_count") != contract.get("quarantined_rows"):
        errors.append("Captured-subset counts changed")
    if actual.get("captured_by_cohort") != contract.get("admitted_by_cohort"):
        errors.append("Captured-subset cohort composition changed")
    if [row.get("availability_plan_id") for row in actual.get("ordered_quarantined_rows", [])] != contract.get("ordered_quarantined_availability_plan_ids"):
        errors.append("Captured-subset quarantine identity changed")
    return {
        "verification_id": QA_ID,
        "status": QA_STATUS if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "view_sha256": sha256_file(view_path)},
        "checks": {
            "full_recomputation_match": actual == expected,
            "captured_count": actual.get("captured_count"),
            "captured_by_cohort": actual.get("captured_by_cohort"),
            "quarantined_count": actual.get("quarantined_count"),
            "quarantined_ids": [row.get("availability_plan_id") for row in actual.get("ordered_quarantined_rows", [])],
        },
        "decision": {
            "offline_exact_text_release_may_be_prepared": not errors,
            "failed_row_remains_quarantined": True,
            "network_access_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--view", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite captured-subset QA")
    result = verify(args.release, args.view)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
