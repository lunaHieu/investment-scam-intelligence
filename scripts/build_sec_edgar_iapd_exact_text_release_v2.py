"""Build an offline exact-text release for a verified captured subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_captured_subset_v1 import VIEW_ID, VIEW_STATUS
from scripts.verify_sec_edgar_iapd_captured_subset_v1 import QA_ID as SUBSET_QA_ID, QA_STATUS as SUBSET_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_EXACT_TEXT_EXTRACTION_RELEASE_V2"


def build_release(
    *, subset_view_path: Path, subset_qa_path: Path, text_root: Path,
    manifest_path: Path, report_path: Path, created_at: str,
) -> dict[str, Any]:
    view = load_object(subset_view_path)
    qa = load_object(subset_qa_path)
    errors: list[str] = []
    if view.get("report_id") != VIEW_ID or view.get("status") != VIEW_STATUS:
        errors.append("Unexpected captured-subset identity or status")
    if qa.get("verification_id") != SUBSET_QA_ID or qa.get("status") != SUBSET_QA_STATUS:
        errors.append("Captured-subset independent QA did not pass")
    if qa.get("inputs", {}).get("view_sha256") != sha256_file(subset_view_path):
        errors.append("Captured-subset QA/view hash mismatch")
    if qa.get("decision", {}).get("offline_exact_text_release_may_be_prepared") is not True:
        errors.append("Captured-subset QA did not release exact-text preparation")
    rows = list(view.get("results", []))
    if not rows or len(rows) != view.get("captured_count") or any(row.get("outcome") != "CAPTURED" for row in rows):
        errors.append("Captured-subset view does not contain exactly the captured population")
    if view.get("quarantined_count", 0) < 1 or view.get("decision", {}).get("quarantined_rows_included") is not False:
        errors.append("Captured-subset quarantine was not preserved")
    for output in (text_root, manifest_path, report_path):
        if output.exists():
            errors.append(f"Frozen exact-text V2 output already exists: {output}")
    if errors:
        raise ValueError(f"Exact-text V2 release validation failed: {errors}")
    return {
        "release_id": RELEASE_ID,
        "created_at": created_at,
        "status": "FROZEN_OFFLINE_CAPTURED_SUBSET_EXACT_TEXT_RELEASE",
        "inputs": {
            "captured_subset_view": {"path": str(subset_view_path.resolve()), "sha256": sha256_file(subset_view_path), "captured_count": len(rows)},
            "captured_subset_qa": {"path": str(subset_qa_path.resolve()), "sha256": sha256_file(subset_qa_path), "required_status": SUBSET_QA_STATUS},
        },
        "population_contract": {
            "captured_rows": len(rows),
            "source_population_rows": view["source_population_count"],
            "quarantined_rows": view["quarantined_count"],
            "ordered_quarantined_availability_plan_ids": [row["availability_plan_id"] for row in view["ordered_quarantined_rows"]],
        },
        "method": {
            "transport_decoder": "src.isi.normalization.wayback_external_text.decode_archived_payload",
            "visible_text_extractor": "src.isi.normalization.external_text.extract_visible_text",
            "text_encoding": "UTF-8",
            "text_file_final_newline_added": False,
            "minimum_non_whitespace_text_characters": 20,
            "below_minimum_policy": "PRESERVE_TEXT_AND_ROUTE_OUT_OF_REVIEWABLE_SET",
            "raw_capture_modification_allowed": False,
            "output_overwrite_allowed": False,
        },
        "outputs": {"text_root": str(text_root.resolve()), "manifest": str(manifest_path.resolve()), "report": str(report_path.resolve())},
        "decision": {
            "offline_exact_text_extraction_allowed_after_release_qa": True,
            "network_access_allowed": False,
            "human_label_review_allowed": False,
            "model_scoring_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset-view", type=Path, required=True)
    parser.add_argument("--subset-qa", type=Path, required=True)
    parser.add_argument("--text-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite exact-text V2 release")
    release = build_release(
        subset_view_path=args.subset_view, subset_qa_path=args.subset_qa,
        text_root=args.text_root, manifest_path=args.manifest,
        report_path=args.report, created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"release_id": RELEASE_ID, "captured_rows": release["population_contract"]["captured_rows"], "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

