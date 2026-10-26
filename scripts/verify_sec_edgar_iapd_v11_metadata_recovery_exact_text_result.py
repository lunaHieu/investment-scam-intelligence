"""Independently regenerate V11 recovery exact-text output bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.extract_sec_edgar_iapd_v11_metadata_recovery_exact_text import REPORT_ID, prepare, sha256_bytes
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


PASS_STATUS = "PASS_V11_METADATA_RECOVERY_EXACT_TEXT_BYTES_REGENERATED_GROUPING_MAY_BE_PREPARED"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        _, prepared, outputs = prepare(release_path, release_qa_path)
    except Exception as error:
        return {"verification_id": "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_EXACT_TEXT_RESULT_INDEPENDENT_QA_V1", "status": "FAIL", "errors": [f"Input revalidation failed: {type(error).__name__}: {error}"]}
    manifest_rows = read_jsonl(outputs["manifest"]) if outputs["manifest"].is_file() else []
    if not outputs["manifest"].is_file():
        errors.append("Recovery exact-text manifest is missing")
    report = load_object(outputs["report"]) if outputs["report"].is_file() else {}
    if not outputs["report"].is_file():
        errors.append("Recovery exact-text report is missing")
    expected = {row["record_id"]: (row, text) for row, text in prepared}
    actual = {row.get("record_id"): row for row in manifest_rows}
    if len(actual) != len(manifest_rows) or set(actual) != set(expected):
        errors.append("Recovery manifest membership differs from regenerated population")
    expected_files: set[Path] = set()
    exact_matches = 0
    for record_id, (expected_row, expected_text) in expected.items():
        row = actual.get(record_id)
        path = Path(str(expected_row["text_path"])).resolve()
        expected_files.add(path)
        if row != expected_row:
            errors.append(f"Recovery manifest metadata mismatch: {record_id}")
        if not path.is_file():
            errors.append(f"Recovery extracted text missing: {record_id}")
            continue
        payload = path.read_bytes()
        if payload != expected_text or sha256_bytes(payload) != expected_row["text_sha256"]:
            errors.append(f"Recovery extracted text byte/hash mismatch: {record_id}")
        else:
            exact_matches += 1
    on_disk = {path.resolve() for path in outputs["text_root"].glob("*.txt") if path.is_file()} if outputs["text_root"].is_dir() else set()
    if on_disk != expected_files:
        errors.append("Recovery exact-text file set differs from manifest")
    passed = sum(row["minimum_content_passed"] for row, _ in prepared)
    counts = report.get("counts", {})
    if report.get("report_id") != REPORT_ID:
        errors.append("Unexpected recovery exact-text report identity")
    if counts.get("extracted_count") != len(prepared) or counts.get("minimum_content_passed_count") != passed or counts.get("below_minimum_preserved_count") != len(prepared) - passed:
        errors.append("Recovery exact-text report aggregate mismatch")
    if report.get("outputs", {}).get("manifest", {}).get("sha256") != (sha256_file(outputs["manifest"]) if outputs["manifest"].is_file() else None):
        errors.append("Recovery exact-text report manifest hash mismatch")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_EXACT_TEXT_RESULT_INDEPENDENT_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "manifest_sha256": sha256_file(outputs["manifest"]) if outputs["manifest"].is_file() else None, "report_sha256": sha256_file(outputs["report"]) if outputs["report"].is_file() else None},
        "checks": {"independently_regenerated_count": len(prepared), "byte_for_byte_match_count": exact_matches, "file_set_matches_manifest": on_disk == expected_files, "minimum_content_passed_count": passed, "below_minimum_preserved_count": len(prepared) - passed, "labels_created": 0},
        "decision": {"exact_text_qa_passed": not errors, "post_capture_grouping_may_be_prepared": not errors, "human_label_review_allowed": False, "model_scoring_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite recovery exact-text result QA")
    result = verify(args.release, args.release_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
