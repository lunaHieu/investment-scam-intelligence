"""Build the exact independently verified captured subset from a partial result."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_capture_result_v1 import verify as verify_capture
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_CAPTURED_SUBSET_ADMISSION_RELEASE_V1"
VIEW_ID = "ISI_SEC_EDGAR_IAPD_CAPTURED_SUBSET_VIEW_V1"
VIEW_STATUS = "COMPLETE_VERIFIED_CAPTURED_SUBSET_WITH_EXPLICIT_QUARANTINE"


def validate_release(
    path: Path, *, require_outputs_absent: bool = True
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    release = load_object(path)
    if release.get("release_id") != RELEASE_ID:
        raise ValueError("Unexpected captured-subset release")
    root = path.resolve().parents[1]
    for item in release.get("basis", []):
        target = root / item["path"]
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            raise ValueError(f"Captured-subset basis mismatch: {item.get('role')}")
    for name, item in release["inputs"].items():
        target = Path(item["path"])
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            raise ValueError(f"Captured-subset input mismatch: {name}")
    report = load_object(Path(release["inputs"]["source_capture_report"]["path"]))
    qa = load_object(Path(release["inputs"]["independent_capture_qa"]["path"]))
    recomputed = verify_capture(
        Path(release["inputs"]["source_capture_release"]["path"]),
        Path(release["inputs"]["source_capture_release_qa"]["path"]),
        Path(release["inputs"]["source_capture_report"]["path"]),
    )
    if qa != recomputed or qa.get("status") != release["inputs"]["independent_capture_qa"]["required_status"]:
        raise ValueError("Partial capture QA is not an exact passing recomputation")
    contract = release["population_contract"]
    captured = [row for row in report["results"] if row.get("outcome") == "CAPTURED"]
    quarantined = [row for row in report["results"] if row.get("outcome") != "CAPTURED"]
    if len(report["results"]) != contract["source_rows"] or len(captured) != contract["admitted_captured_rows"]:
        raise ValueError("Captured-subset population changed")
    if dict(Counter(row["cohort"] for row in captured)) != contract["admitted_by_cohort"]:
        raise ValueError("Captured-subset cohort composition changed")
    if [row["availability_plan_id"] for row in quarantined] != contract["ordered_quarantined_availability_plan_ids"]:
        raise ValueError("Captured-subset quarantine identity/order changed")
    for row in captured:
        target = Path(row["capture_path"])
        if not target.is_file() or target.stat().st_size != row["bytes"] or sha256_file(target) != row["sha256"]:
            raise ValueError(f"Captured raw byte/hash changed: {row['availability_plan_id']}")
    if require_outputs_absent:
        for output in release["outputs"].values():
            if Path(output).exists() or Path(output).with_suffix(Path(output).suffix + ".partial").exists():
                raise FileExistsError(f"Captured-subset output already exists: {output}")
    return release, report, qa


def build(release_path: Path, *, require_outputs_absent: bool = True) -> dict[str, Any]:
    release, report, qa = validate_release(
        release_path, require_outputs_absent=require_outputs_absent
    )
    captured = [row for row in report["results"] if row.get("outcome") == "CAPTURED"]
    quarantined = [row for row in report["results"] if row.get("outcome") != "CAPTURED"]
    return {
        "report_id": VIEW_ID,
        "created_at": release["created_at"],
        "status": VIEW_STATUS,
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "source_capture_report": release["inputs"]["source_capture_report"],
        "source_capture_qa": release["inputs"]["independent_capture_qa"],
        "source_population_count": len(report["results"]),
        "captured_count": len(captured),
        "captured_by_cohort": dict(Counter(row["cohort"] for row in captured)),
        "quarantined_count": len(quarantined),
        "ordered_quarantined_rows": [
            {
                "availability_plan_id": row["availability_plan_id"],
                "cohort": row["cohort"],
                "candidate_host": row["candidate_host"],
                "prior_outcome": row["outcome"],
                "prior_error": row["error"],
            }
            for row in quarantined
        ],
        "results": captured,
        "decision": {
            "offline_exact_text_release_may_be_prepared_after_independent_subset_qa": True,
            "quarantined_rows_included": False,
            "network_access_allowed": False,
            "labels_created": 0,
            "training_allowed": False,
        },
        "safety_contract": qa["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    args = parser.parse_args()
    release = load_object(args.release)
    output = Path(release["outputs"]["captured_subset_view"])
    view = build(args.release)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    partial.write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(output)
    print(json.dumps({"report_id": VIEW_ID, "captured_count": view["captured_count"], "quarantined_count": view["quarantined_count"], "sha256": sha256_file(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

