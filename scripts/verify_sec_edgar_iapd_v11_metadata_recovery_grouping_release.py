"""Independently verify the V11 recovery grouping release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_grouping_release import RELEASE_ID, TEXT_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


PASS_STATUS = "PASS_OFFLINE_V11_METADATA_RECOVERY_GROUPING_RELEASE"


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected recovery grouping release identity")
    loaded: dict[str, Any] = {}
    for role, item in release.get("inputs", {}).items():
        path = Path(str(item.get("path", "")))
        try:
            if sha256_file(path) != item.get("sha256"):
                errors.append(f"Recovery grouping input hash mismatch: {role}")
            loaded[role] = load_object(path) if path.suffix == ".json" else None
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"Cannot read recovery grouping input {role}: {error}")
    text_qa = loaded.get("exact_text_result_qa") or {}
    if text_qa.get("status") != TEXT_QA_STATUS or text_qa.get("checks", {}).get("independently_regenerated_count") != 2:
        errors.append("Recovery exact-text QA population/status changed")
    contract = release.get("population_contract", {})
    if contract.get("supplemental_rows") != 2 or contract.get("cohort") != "EXTERNAL_HOLDOUT" or contract.get("minimum_content_pass_rows", 0) + contract.get("below_minimum_rows", 0) != 2:
        errors.append("Recovery grouping population contract changed")
    opened = loaded.get("opened_external_exclusion_index") or {}
    remediation = loaded.get("legacy_group_remediation_map") or {}
    if opened.get("counts", {}).get("opened_records") != 107 or remediation.get("counts", {}).get("legacy_records") != 86:
        errors.append("Frozen exclusion/remediation population changed")
    expected_method = {"word_shingle_size": 5, "jaccard_threshold": 0.8, "containment_threshold": 0.95, "minimum_shorter_shingles_for_containment_rule": 20, "component_algorithm": "DETERMINISTIC_TRANSITIVE_UNION_FIND", "holdout_collision_policy": "ROUTE_HOLDOUT_MEMBER_OUT_OF_INDEPENDENT_HOLDOUT"}
    for key, value in expected_method.items():
        if release.get("method", {}).get(key) != value:
            errors.append(f"Recovery grouping method changed: {key}")
    output = Path(str(release.get("output", {}).get("path", "")))
    if output.exists() or output.with_suffix(output.suffix + ".partial").exists():
        errors.append("Recovery grouping output already exists")
    for gate in ("network_access_allowed", "human_label_review_allowed", "model_scoring_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if release.get("decision", {}).get(gate) is not False:
            errors.append(f"Forbidden recovery grouping gate opened: {gate}")
    return {"verification_id": "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_GROUPING_RELEASE_INDEPENDENT_QA_V1", "status": PASS_STATUS if not errors else "FAIL", "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)}, "checks": {"manifest_rows": 2, "minimum_content_pass_rows": contract.get("minimum_content_pass_rows"), "below_minimum_rows": contract.get("below_minimum_rows"), "opened_rows": 107, "legacy_remediation_rows": 86, "output_absent": not output.exists()}, "decision": {"release_qa_passed": not errors, "offline_grouping_allowed": not errors, "human_label_review_allowed": False, "training_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "labels": 0, "model": 0}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite recovery grouping release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
