"""Independently verify a captured-subset exact-text V2 release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_sec_edgar_iapd_captured_subset_v1 import VIEW_ID, VIEW_STATUS
from scripts.build_sec_edgar_iapd_exact_text_release_v2 import RELEASE_ID
from scripts.verify_sec_edgar_iapd_captured_subset_v1 import QA_ID as SUBSET_QA_ID, QA_STATUS as SUBSET_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


QA_STATUS = "PASS_OFFLINE_CAPTURED_SUBSET_EXACT_TEXT_RELEASE_V2"


def verify(release_path: Path) -> dict:
    release = load_object(release_path)
    errors = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected exact-text V2 release identity")
    view_item = release.get("inputs", {}).get("captured_subset_view", {})
    qa_item = release.get("inputs", {}).get("captured_subset_qa", {})
    view_path, qa_path = Path(str(view_item.get("path", ""))), Path(str(qa_item.get("path", "")))
    try:
        if sha256_file(view_path) != view_item.get("sha256"):
            errors.append("Captured-subset view hash mismatch")
        if sha256_file(qa_path) != qa_item.get("sha256"):
            errors.append("Captured-subset QA hash mismatch")
        view, qa = load_object(view_path), load_object(qa_path)
    except Exception as error:
        view, qa = {}, {}
        errors.append(f"Cannot read exact-text V2 inputs: {type(error).__name__}: {error}")
    if view.get("report_id") != VIEW_ID or view.get("status") != VIEW_STATUS:
        errors.append("Captured-subset view identity changed")
    if qa.get("verification_id") != SUBSET_QA_ID or qa.get("status") != SUBSET_QA_STATUS or qa.get("inputs", {}).get("view_sha256") != view_item.get("sha256"):
        errors.append("Captured-subset QA status or binding changed")
    population = release.get("population_contract", {})
    if population.get("captured_rows") != view.get("captured_count") or population.get("quarantined_rows") != view.get("quarantined_count"):
        errors.append("Exact-text V2 population contract changed")
    if population.get("ordered_quarantined_availability_plan_ids") != [row.get("availability_plan_id") for row in view.get("ordered_quarantined_rows", [])]:
        errors.append("Exact-text V2 quarantine identity changed")
    method = release.get("method", {})
    if method.get("minimum_non_whitespace_text_characters") != 20 or method.get("raw_capture_modification_allowed") is not False or method.get("output_overwrite_allowed") is not False:
        errors.append("Exact-text V2 method or immutability contract changed")
    outputs = [Path(str(release.get("outputs", {}).get(key, ""))) for key in ("text_root", "manifest", "report")]
    if any(path.exists() for path in outputs):
        errors.append("One or more exact-text V2 outputs already exist")
    decision = release.get("decision", {})
    if decision.get("offline_exact_text_extraction_allowed_after_release_qa") is not True:
        errors.append("Offline exact-text V2 gate is closed")
    for gate in ("network_access_allowed", "human_label_review_allowed", "model_scoring_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden exact-text V2 gate opened: {gate}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_EXACT_TEXT_RELEASE_INDEPENDENT_QA_V2",
        "status": QA_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {"captured_rows": population.get("captured_rows"), "quarantined_rows": population.get("quarantined_rows"), "outputs_absent": not any(path.exists() for path in outputs)},
        "decision": {"release_qa_passed": not errors, "offline_extraction_allowed": not errors, "network_access_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite exact-text V2 release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
