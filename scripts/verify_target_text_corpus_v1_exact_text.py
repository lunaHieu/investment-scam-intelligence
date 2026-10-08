"""Independently regenerate and verify Target Text Corpus V1 exact-text outputs."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.extract_target_text_corpus_v1_exact_text import (
    load_json,
    load_jsonl,
    prepare_extraction,
    sha256_bytes,
    sha256_file,
)


def verify(config_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        config, independently_prepared, outputs = prepare_extraction(config_path)
    except Exception as error:  # Returned as audit evidence instead of hiding the failure.
        return {
            "review_id": "ISI_TARGET_TEXT_CORPUS_V1_EXACT_TEXT_INDEPENDENT_QA_V1",
            "status": "FAIL",
            "errors": [f"Input revalidation failed: {type(error).__name__}: {error}"],
        }

    if not outputs["manifest"].is_file():
        errors.append("Extraction manifest missing")
        manifest_rows: list[dict[str, Any]] = []
    else:
        manifest_rows = load_jsonl(outputs["manifest"])
    if not outputs["report"].is_file():
        errors.append("Extraction report missing")
        report: dict[str, Any] = {}
    else:
        report = load_json(outputs["report"])

    expected_by_id = {str(row["candidate_id"]): (row, text) for row, text in independently_prepared}
    actual_by_id: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        candidate_id = str(row.get("candidate_id", ""))
        if candidate_id in actual_by_id:
            errors.append(f"Duplicate manifest candidate: {candidate_id}")
        actual_by_id[candidate_id] = row
    if set(actual_by_id) != set(expected_by_id):
        errors.append("Manifest candidate membership differs from independently regenerated population")

    expected_files: set[Path] = set()
    exact_matches = 0
    for candidate_id, (expected, expected_text) in expected_by_id.items():
        actual = actual_by_id.get(candidate_id)
        expected_path = Path(str(expected["text_path"])).resolve()
        expected_files.add(expected_path)
        if actual is None:
            continue
        if actual != expected:
            errors.append(f"Manifest metadata mismatch: {candidate_id}")
        if not expected_path.is_file():
            errors.append(f"Extracted text missing: {candidate_id}")
            continue
        actual_text = expected_path.read_bytes()
        if actual_text != expected_text:
            errors.append(f"Extracted text byte mismatch: {candidate_id}")
            continue
        if sha256_bytes(actual_text) != actual.get("text_sha256"):
            errors.append(f"Extracted text hash mismatch: {candidate_id}")
            continue
        exact_matches += 1

    on_disk = {
        path.resolve() for path in outputs["text_root"].glob("*.txt") if path.is_file()
    } if outputs["text_root"].is_dir() else set()
    if on_disk != expected_files:
        errors.append("Exact-text directory contains missing or unregistered .txt files")
    extra_files = {
        path.resolve() for path in outputs["text_root"].rglob("*") if path.is_file()
    } - expected_files if outputs["text_root"].is_dir() else set()
    if extra_files:
        errors.append("Exact-text directory contains unexpected non-manifest files")

    expected_passed = sum(
        bool(row["minimum_content_passed"]) for row, _ in independently_prepared
    )
    expected_below = len(independently_prepared) - expected_passed
    counts = report.get("counts", {})
    if report.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_EXACT_TEXT_EXTRACTION_REPORT_V1":
        errors.append("Unexpected extraction report ID")
    if counts.get("extracted_count") != len(independently_prepared):
        errors.append("Extraction report count mismatch")
    if counts.get("minimum_content_passed_count") != expected_passed:
        errors.append("Minimum-content pass count mismatch")
    if counts.get("below_minimum_preserved_count") != expected_below:
        errors.append("Below-minimum count mismatch")
    if report.get("outputs", {}).get("manifest", {}).get("sha256") != (
        sha256_file(outputs["manifest"]) if outputs["manifest"].is_file() else None
    ):
        errors.append("Extraction report manifest hash mismatch")
    if report.get("gates", {}).get("human_label_review_allowed") is not False:
        errors.append("Human-label gate unexpectedly open")

    by_channel = Counter(
        str(row["channel_id"]) for row, _ in independently_prepared
        if row["minimum_content_passed"]
    )
    below_ids = sorted(
        str(row["candidate_id"]) for row, _ in independently_prepared
        if not row["minimum_content_passed"]
    )
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_EXACT_TEXT_INDEPENDENT_QA_V1",
        "status": "PASS_EXACT_TEXT_BYTES_REGENERATED" if not errors else "FAIL",
        "inputs": {
            "config": {"path": str(config_path), "sha256": sha256_file(config_path)},
            "manifest": {
                "path": str(outputs["manifest"]),
                "sha256": sha256_file(outputs["manifest"]) if outputs["manifest"].is_file() else None,
            },
            "report": {
                "path": str(outputs["report"]),
                "sha256": sha256_file(outputs["report"]) if outputs["report"].is_file() else None,
            },
        },
        "checks": {
            "independently_regenerated_count": len(independently_prepared),
            "byte_for_byte_match_count": exact_matches,
            "file_set_matches_manifest": on_disk == expected_files and not extra_files,
            "minimum_content_passed_count": expected_passed,
            "below_minimum_preserved_count": expected_below,
            "minimum_content_passed_by_channel": dict(sorted(by_channel.items())),
            "below_minimum_candidate_ids": below_ids,
            "raw_capture_modifications": 0,
            "labels_created": 0,
        },
        "decision": {
            "exact_text_qa_passed": not errors,
            "post_capture_exclusion_and_grouping_allowed": not errors,
            "human_label_review_allowed": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": config["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    result = verify(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
