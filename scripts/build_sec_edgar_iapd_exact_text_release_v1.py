"""Build an offline exact-text extraction release from a complete capture QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_EXACT_TEXT_EXTRACTION_RELEASE_V1"
CAPTURE_QA_STATUS = "PASS_COMPLETE_TEXT_EXTRACTION_RELEASE_MAY_BE_PREPARED"


def build_release(
    *, capture_report_path: Path, capture_qa_path: Path, text_root: Path,
    manifest_path: Path, report_path: Path, created_at: str,
) -> dict[str, Any]:
    capture_report = load_object(capture_report_path)
    capture_qa = load_object(capture_qa_path)
    errors: list[str] = []
    if capture_qa.get("status") != CAPTURE_QA_STATUS:
        errors.append("Capture result QA did not pass the complete gate")
    if capture_qa.get("inputs", {}).get("report_sha256") != sha256_file(capture_report_path):
        errors.append("Capture result QA/report hash mismatch")
    if capture_qa.get("decision", {}).get("text_extraction_release_may_be_prepared") is not True:
        errors.append("Capture QA did not release exact-text preparation")
    if capture_report.get("status") != "COMPLETE":
        errors.append("Capture report is not complete")
    captured = [row for row in capture_report.get("results", []) if row.get("outcome") == "CAPTURED"]
    if not captured or len(captured) != capture_report.get("planned_capture_count"):
        errors.append("Capture report does not contain the complete captured population")
    for path in (text_root, manifest_path, report_path):
        if path.exists():
            errors.append(f"Frozen extraction output already exists: {path}")
    if errors:
        raise ValueError(f"Exact-text release validation failed: {errors}")
    return {
        "release_id": RELEASE_ID,
        "created_at": created_at,
        "status": "FROZEN_OFFLINE_EXACT_TEXT_EXTRACTION_RELEASE",
        "inputs": {
            "capture_report": {"path": str(capture_report_path.resolve()), "sha256": sha256_file(capture_report_path), "captured_count": len(captured)},
            "capture_result_qa": {"path": str(capture_qa_path.resolve()), "sha256": sha256_file(capture_qa_path), "required_status": CAPTURE_QA_STATUS},
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
        "outputs": {
            "text_root": str(text_root.resolve()),
            "manifest": str(manifest_path.resolve()),
            "report": str(report_path.resolve()),
        },
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
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--capture-qa", type=Path, required=True)
    parser.add_argument("--text-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite exact-text release")
    release = build_release(
        capture_report_path=args.capture_report, capture_qa_path=args.capture_qa,
        text_root=args.text_root, manifest_path=args.manifest,
        report_path=args.report, created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"release_id": RELEASE_ID, "output": str(args.output), "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
