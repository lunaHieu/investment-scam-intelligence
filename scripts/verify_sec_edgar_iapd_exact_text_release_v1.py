"""Independently verify a SEC/IAPD offline exact-text extraction release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_exact_text_release_v1 import CAPTURE_QA_STATUS, RELEASE_ID
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected exact-text release identity")
    report_path = Path(str(release.get("inputs", {}).get("capture_report", {}).get("path", "")))
    qa_path = Path(str(release.get("inputs", {}).get("capture_result_qa", {}).get("path", "")))
    try:
        if sha256_file(report_path) != release["inputs"]["capture_report"]["sha256"]:
            errors.append("Capture report hash mismatch")
        if sha256_file(qa_path) != release["inputs"]["capture_result_qa"]["sha256"]:
            errors.append("Capture result QA hash mismatch")
        report, qa = load_object(report_path), load_object(qa_path)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        report, qa = {}, {}
        errors.append(f"Cannot read release evidence: {error}")
    if report.get("status") != "COMPLETE" or report.get("captured_count") != report.get("planned_capture_count"):
        errors.append("Capture population is not complete")
    if qa.get("status") != CAPTURE_QA_STATUS or qa.get("inputs", {}).get("report_sha256") != release.get("inputs", {}).get("capture_report", {}).get("sha256"):
        errors.append("Capture QA status or binding mismatch")
    method = release.get("method", {})
    if method.get("minimum_non_whitespace_text_characters") != 20:
        errors.append("Minimum content threshold changed")
    if method.get("raw_capture_modification_allowed") is not False or method.get("output_overwrite_allowed") is not False:
        errors.append("Extraction immutability contract changed")
    outputs = [Path(str(release.get("outputs", {}).get(key, ""))) for key in ("text_root", "manifest", "report")]
    if any(path.exists() for path in outputs):
        errors.append("One or more frozen extraction outputs already exist")
    decision = release.get("decision", {})
    if decision.get("offline_exact_text_extraction_allowed_after_release_qa") is not True:
        errors.append("Offline extraction gate is closed")
    for gate in ("network_access_allowed", "human_label_review_allowed", "model_scoring_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden exact-text gate opened: {gate}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_EXACT_TEXT_RELEASE_INDEPENDENT_QA_V1",
        "status": "PASS_OFFLINE_EXACT_TEXT_RELEASE" if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {"captured_count": report.get("captured_count"), "minimum_non_whitespace_text_characters": method.get("minimum_non_whitespace_text_characters"), "outputs_absent": not any(path.exists() for path in outputs)},
        "decision": {"release_qa_passed": not errors, "offline_extraction_allowed": not errors, "network_access_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite exact-text release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
