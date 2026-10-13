"""Independently verify a SEC/IAPD offline grouping release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_grouping_release_v1 import RELEASE_ID, TEXT_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected grouping release identity")
    inputs: dict[str, Any] = {}
    for role, item in release.get("inputs", {}).items():
        path = Path(str(item.get("path", "")))
        try:
            if sha256_file(path) != item.get("sha256"):
                errors.append(f"Grouping input hash mismatch: {role}")
            inputs[role] = load_object(path) if path.suffix == ".json" else None
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"Cannot read grouping input {role}: {error}")
    text_qa = inputs.get("exact_text_result_qa") or {}
    if text_qa.get("status") != TEXT_QA_STATUS:
        errors.append("Exact-text result QA status changed")
    opened = inputs.get("opened_external_exclusion_index") or {}
    remediation = inputs.get("legacy_group_remediation_map") or {}
    if opened.get("counts", {}).get("opened_records") != 107 or remediation.get("counts", {}).get("legacy_records") != 86:
        errors.append("Frozen exclusion/remediation population changed")
    method = release.get("method", {})
    expected = {"word_shingle_size": 5, "jaccard_threshold": 0.8, "containment_threshold": 0.95, "minimum_shorter_shingles_for_containment_rule": 20, "component_algorithm": "DETERMINISTIC_TRANSITIVE_UNION_FIND", "holdout_collision_policy": "ROUTE_HOLDOUT_MEMBER_OUT_OF_INDEPENDENT_HOLDOUT"}
    for key, value in expected.items():
        if method.get(key) != value:
            errors.append(f"Grouping method changed: {key}")
    output = Path(str(release.get("output", {}).get("path", "")))
    if output.exists() or output.with_suffix(output.suffix + ".partial").exists():
        errors.append("Grouping output already exists")
    decision = release.get("decision", {})
    for gate in ("network_access_allowed", "human_label_review_allowed", "model_scoring_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"Forbidden grouping gate opened: {gate}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_GROUPING_RELEASE_INDEPENDENT_QA_V1",
        "status": "PASS_OFFLINE_GROUPING_RELEASE" if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {"manifest_rows": release.get("inputs", {}).get("exact_text_manifest", {}).get("record_count"), "opened_rows": 107, "legacy_remediation_rows": 86, "output_absent": not output.exists()},
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
        raise FileExistsError("Refusing to overwrite grouping release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
