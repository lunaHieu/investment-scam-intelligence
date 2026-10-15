"""Recompute complete raw provenance after the historical capture anchor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.audit_raw_cross_registry_provenance_v1 import REPO_ROOT, build_report, sha256_file


ANCHOR = REPO_ROOT / "registry" / "analyses" / "historical_raw_capture_integrity_anchor_v1.json"
ANCHOR_SHA256 = "e0db6e62a058e33ccf3e1e61ae016831e8b37808a781a94f7cc7ed6c2882c69d"


def finalize_v2(report: dict[str, Any]) -> dict[str, Any]:
    summary = report["summary"]
    complete_existing = (
        summary["verified_hash_pinned_chain_files"] == summary["raw_file_count"]
        and summary["no_hash_pinned_chain_found_files"] == 0
        and summary["hash_mismatch_files"] == 0
        and summary["mismatched_raw_claim_count"] == 0
    )
    report["audit_id"] = "ISI_RAW_CROSS_REGISTRY_PROVENANCE_AUDIT_V2"
    report["status"] = (
        "PASS_COMPLETE_EXISTING_RAW_PROVENANCE"
        if complete_existing
        else "FAIL_EXISTING_RAW_PROVENANCE_INCOMPLETE"
    )
    report["input_anchor"] = {
        "path": str(ANCHOR),
        "sha256": ANCHOR_SHA256,
        "role": "retrospective_integrity_anchor_no_promotion",
    }
    report["decision"] = {
        "complete_existing_raw_file_provenance_chain": complete_existing,
        "historical_missing_claim_targets_resolved": summary["missing_raw_claim_target_count"] == 0,
        "existing_raw_hash_mismatch_detected": summary["mismatched_raw_claim_count"] != 0,
        "files_promoted": 0,
        "training_allowed": False,
        "validation_or_test_opening_allowed": False,
        "labeling_allowed": False,
        "next_gate": (
            "Update the project state ledger and continue non-model data readiness branches; preserve separately reported missing historical claim targets."
            if complete_existing
            else "Resolve remaining existing-raw provenance gaps without manufacturing evidence."
        ),
    }
    return report


def build_report_v2() -> dict[str, Any]:
    if sha256_file(ANCHOR) != ANCHOR_SHA256:
        raise ValueError("Historical capture integrity anchor hash mismatch")
    return finalize_v2(build_report())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite raw cross-registry provenance audit V2")
    report = build_report_v2()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({key: report[key] for key in ("audit_id", "status", "scope", "summary", "decision")}, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
