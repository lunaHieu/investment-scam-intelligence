"""Prepare (but do not open) the V11 supplemental exact-text release gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_EXACT_TEXT_RELEASE_V1"
STRICT_CAPTURE_QA_STATUS = "PASS_COMPLETE_V11_SUPPLEMENTAL_CAPTURE_TEXT_EXTRACTION_MAY_BE_PREPARED"


def build_release(*, capture_report_path: Path, capture_qa_path: Path, text_root: Path, manifest_path: Path, report_path: Path, created_at: str) -> dict[str, Any]:
    report = load_object(capture_report_path)
    qa = load_object(capture_qa_path)
    errors: list[str] = []
    if qa.get("status") != STRICT_CAPTURE_QA_STATUS:
        errors.append("Strict supplemental capture QA has not released exact-text preparation")
    if qa.get("decision", {}).get("text_extraction_release_may_be_prepared") is not True:
        errors.append("Capture QA decision does not release exact-text preparation")
    if qa.get("inputs", {}).get("report_sha256") != sha256_file(capture_report_path):
        errors.append("Capture report/QA hash mismatch")
    if report.get("status") != "COMPLETE":
        errors.append("Capture report is not strict COMPLETE")
    rows = list(report.get("results", []))
    if not rows or any(row.get("outcome") != "CAPTURED" for row in rows):
        errors.append("Capture rows are not all strict CAPTURED")
    for output in (text_root, manifest_path, report_path):
        if output.exists():
            errors.append(f"Exact-text output already exists: {output}")
    if errors:
        raise ValueError(f"V11 supplemental exact-text release blocked: {errors}")
    return {
        "release_id": RELEASE_ID,
        "created_at": created_at,
        "status": "FROZEN_V11_SUPPLEMENTAL_OFFLINE_EXACT_TEXT_RELEASE",
        "inputs": {"capture_report": {"path": str(capture_report_path.resolve()), "sha256": sha256_file(capture_report_path), "record_count": len(rows)}, "capture_qa": {"path": str(capture_qa_path.resolve()), "sha256": sha256_file(capture_qa_path), "required_status": STRICT_CAPTURE_QA_STATUS}},
        "outputs": {"text_root": str(text_root.resolve()), "manifest": str(manifest_path.resolve()), "report": str(report_path.resolve())},
        "method": {"transport_decoder": "src.isi.normalization.wayback_external_text.decode_archived_payload", "visible_text_extractor": "src.isi.normalization.external_text.extract_visible_text", "minimum_non_whitespace_text_characters": 20, "below_minimum_policy": "PRESERVE_AND_ROUTE_OUT"},
        "decision": {"offline_exact_text_extraction_allowed_after_release_qa": True, "network_access_allowed": False, "grouping_allowed": False, "labeling_allowed": False, "validation_or_test_opening_allowed": False, "training_allowed": False},
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
        raise FileExistsError("Refusing to overwrite supplemental exact-text release")
    release = build_release(capture_report_path=args.capture_report, capture_qa_path=args.capture_qa, text_root=args.text_root, manifest_path=args.manifest, report_path=args.report, created_at=args.created_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".partial")
    tmp.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(json.dumps({"release_id": RELEASE_ID, "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
