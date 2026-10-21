"""Independently verify the captured-subset grouping V2 release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_grouping_release_v2 import RELEASE_ID, TEXT_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected grouping V2 release identity")
    loaded: dict[str, Any] = {}
    for role, item in release.get("inputs", {}).items():
        path = Path(str(item.get("path", "")))
        try:
            if sha256_file(path) != item.get("sha256"):
                errors.append(f"Grouping input hash mismatch: {role}")
            loaded[role] = load_object(path) if path.suffix == ".json" else None
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"Cannot read grouping input {role}: {error}")
    text_qa = loaded.get("exact_text_result_qa") or {}
    if text_qa.get("status") != TEXT_QA_STATUS:
        errors.append("Captured-subset exact-text QA status changed")
    if text_qa.get("checks", {}).get("independently_regenerated_count") != 57:
        errors.append("Captured-subset manifest population changed")
    if text_qa.get("checks", {}).get("minimum_content_passed_count") != 56:
        errors.append("Reviewable exact-text population changed")
    contract = release.get("population_contract", {})
    expected_contract = {
        "source_capture_plan_rows": 58,
        "captured_subset_rows": 57,
        "minimum_content_pass_rows": 56,
        "below_minimum_rows": 1,
        "capture_quarantined_rows": 1,
        "ordered_capture_quarantine_ids": ["TTCV1_EDGAR_AVAIL_DEV_037"],
        "below_minimum_policy": "PRESERVE_AND_ROUTE_OUT_OF_REVIEWABLE_SET",
    }
    if contract != expected_contract:
        errors.append("Grouping V2 population/quarantine contract changed")
    opened = loaded.get("opened_external_exclusion_index") or {}
    remediation = loaded.get("legacy_group_remediation_map") or {}
    if opened.get("counts", {}).get("opened_records") != 107 or remediation.get("counts", {}).get("legacy_records") != 86:
        errors.append("Frozen exclusion/remediation population changed")
    expected_method = {"word_shingle_size": 5, "jaccard_threshold": 0.8, "containment_threshold": 0.95, "minimum_shorter_shingles_for_containment_rule": 20, "component_algorithm": "DETERMINISTIC_TRANSITIVE_UNION_FIND", "holdout_collision_policy": "ROUTE_HOLDOUT_MEMBER_OUT_OF_INDEPENDENT_HOLDOUT"}
    for key, value in expected_method.items():
        if release.get("method", {}).get(key) != value:
            errors.append(f"Grouping method changed: {key}")
    output = Path(str(release.get("output", {}).get("path", "")))
    if output.exists() or output.with_suffix(output.suffix + ".partial").exists():
        errors.append("Grouping output already exists")
    for gate in ("network_access_allowed", "human_label_review_allowed", "model_scoring_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if release.get("decision", {}).get(gate) is not False:
            errors.append(f"Forbidden grouping gate opened: {gate}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_GROUPING_RELEASE_INDEPENDENT_QA_V2",
        "status": "PASS_OFFLINE_CAPTURED_SUBSET_GROUPING_RELEASE" if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {"manifest_rows": 57, "reviewable_rows": 56, "capture_quarantined_rows": 1, "opened_rows": 107, "legacy_remediation_rows": 86, "output_absent": not output.exists()},
        "decision": {"release_qa_passed": not errors, "offline_grouping_allowed": not errors, "human_label_review_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite grouping V2 release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
