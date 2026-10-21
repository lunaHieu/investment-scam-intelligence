"""Independently regenerate and verify captured-subset exact-text V2 bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.extract_sec_edgar_iapd_exact_text_v2 import prepare, sha256_bytes
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(release_path: Path, release_qa_path: Path) -> dict:
    errors = []
    try:
        release, prepared, outputs = prepare(release_path, release_qa_path)
    except Exception as error:
        return {"verification_id": "ISI_SEC_EDGAR_IAPD_EXACT_TEXT_RESULT_INDEPENDENT_QA_V2", "status": "FAIL", "errors": [f"Input revalidation failed: {type(error).__name__}: {error}"]}
    manifest_rows = read_jsonl(outputs["manifest"]) if outputs["manifest"].is_file() else []
    report = load_object(outputs["report"]) if outputs["report"].is_file() else {}
    expected = {row["record_id"]: (row, payload) for row, payload in prepared}
    actual = {row.get("record_id"): row for row in manifest_rows}
    if len(actual) != len(manifest_rows) or set(actual) != set(expected):
        errors.append("Manifest membership differs from regenerated population")
    expected_files = set()
    exact_matches = 0
    for record_id, (expected_row, expected_payload) in expected.items():
        row = actual.get(record_id)
        path = Path(expected_row["text_path"]).resolve()
        expected_files.add(path)
        if row != expected_row:
            errors.append(f"Manifest metadata mismatch: {record_id}")
        if not path.is_file():
            errors.append(f"Extracted text missing: {record_id}")
            continue
        payload = path.read_bytes()
        if payload != expected_payload or sha256_bytes(payload) != expected_row["text_sha256"]:
            errors.append(f"Extracted text byte/hash mismatch: {record_id}")
        else:
            exact_matches += 1
    on_disk = {path.resolve() for path in outputs["text_root"].glob("*.txt") if path.is_file()} if outputs["text_root"].is_dir() else set()
    if on_disk != expected_files:
        errors.append("Exact-text V2 file set differs from manifest")
    passed = sum(row["minimum_content_passed"] for row, _ in prepared)
    counts = report.get("counts", {})
    if report.get("report_id") != "ISI_SEC_EDGAR_IAPD_EXACT_TEXT_EXTRACTION_REPORT_V2":
        errors.append("Unexpected exact-text V2 report identity")
    if report.get("population_contract") != release.get("population_contract"):
        errors.append("Exact-text V2 quarantine/population contract changed")
    if counts.get("extracted_count") != len(prepared) or counts.get("minimum_content_passed_count") != passed or counts.get("below_minimum_preserved_count") != len(prepared) - passed:
        errors.append("Exact-text V2 report aggregate mismatch")
    if report.get("outputs", {}).get("manifest", {}).get("sha256") != (sha256_file(outputs["manifest"]) if outputs["manifest"].is_file() else None):
        errors.append("Exact-text V2 report manifest hash mismatch")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_EXACT_TEXT_RESULT_INDEPENDENT_QA_V2",
        "status": "PASS_CAPTURED_SUBSET_EXACT_TEXT_BYTES_REGENERATED_GROUPING_MAY_BE_PREPARED" if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "manifest_sha256": sha256_file(outputs["manifest"]) if outputs["manifest"].is_file() else None, "report_sha256": sha256_file(outputs["report"]) if outputs["report"].is_file() else None},
        "checks": {"independently_regenerated_count": len(prepared), "byte_for_byte_match_count": exact_matches, "file_set_matches_manifest": on_disk == expected_files, "minimum_content_passed_count": passed, "below_minimum_preserved_count": len(prepared) - passed, "quarantined_rows": release["population_contract"]["quarantined_rows"], "labels_created": 0},
        "decision": {"exact_text_qa_passed": not errors, "post_capture_grouping_may_be_prepared": not errors, "failed_capture_row_remains_quarantined": True, "human_label_review_allowed": False, "model_scoring_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite exact-text V2 result QA")
    result = verify(args.release, args.release_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
