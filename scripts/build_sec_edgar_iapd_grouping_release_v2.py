"""Build the V2 grouping release for the admitted captured subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_SEC_EDGAR_IAPD_POST_CAPTURE_GROUPING_RELEASE_V2"
TEXT_QA_STATUS = "PASS_CAPTURED_SUBSET_EXACT_TEXT_BYTES_REGENERATED_GROUPING_MAY_BE_PREPARED"


def build_release(
    *, manifest_path: Path, text_qa_path: Path, opened_index_path: Path,
    legacy_remediation_path: Path, output_path: Path, created_at: str,
) -> dict[str, Any]:
    text_qa = load_object(text_qa_path)
    opened = load_object(opened_index_path)
    remediation = load_object(legacy_remediation_path)
    errors: list[str] = []
    if text_qa.get("status") != TEXT_QA_STATUS or text_qa.get("decision", {}).get("post_capture_grouping_may_be_prepared") is not True:
        errors.append("Captured-subset exact-text QA did not release grouping preparation")
    if text_qa.get("inputs", {}).get("manifest_sha256") != sha256_file(manifest_path):
        errors.append("Exact-text QA/manifest hash mismatch")
    if text_qa.get("checks", {}).get("quarantined_rows") != 1:
        errors.append("Capture quarantine population changed")
    if opened.get("counts", {}).get("opened_records") != 107:
        errors.append("Opened external exclusion population changed")
    if remediation.get("counts", {}).get("legacy_records") != 86:
        errors.append("Legacy remediation population changed")
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        errors.append("Grouping output already exists")
    if errors:
        raise ValueError(f"Grouping V2 release validation failed: {errors}")
    return {
        "release_id": RELEASE_ID,
        "created_at": created_at,
        "status": "FROZEN_OFFLINE_CAPTURED_SUBSET_EXCLUSION_GROUPING_RELEASE",
        "inputs": {
            "exact_text_manifest": {
                "path": str(manifest_path.resolve()),
                "sha256": sha256_file(manifest_path),
                "record_count": text_qa["checks"]["independently_regenerated_count"],
                "minimum_content_passed_count": text_qa["checks"]["minimum_content_passed_count"],
            },
            "exact_text_result_qa": {"path": str(text_qa_path.resolve()), "sha256": sha256_file(text_qa_path), "required_status": TEXT_QA_STATUS},
            "opened_external_exclusion_index": {"path": str(opened_index_path.resolve()), "sha256": sha256_file(opened_index_path), "record_count": 107},
            "legacy_group_remediation_map": {"path": str(legacy_remediation_path.resolve()), "sha256": sha256_file(legacy_remediation_path), "record_count": 86},
        },
        "population_contract": {
            "source_capture_plan_rows": 58,
            "captured_subset_rows": 57,
            "minimum_content_pass_rows": 56,
            "below_minimum_rows": 1,
            "capture_quarantined_rows": 1,
            "ordered_capture_quarantine_ids": ["TTCV1_EDGAR_AVAIL_DEV_037"],
            "below_minimum_policy": "PRESERVE_AND_ROUTE_OUT_OF_REVIEWABLE_SET",
        },
        "method": {
            "unicode_normalization": "NFKC_CASEFOLD",
            "word_shingle_size": 5,
            "jaccard_threshold": 0.8,
            "containment_threshold": 0.95,
            "minimum_shorter_shingles_for_containment_rule": 20,
            "internal_edges": ["exact_normalized_host", "exact_text_sha256", "frozen_normalized_near_duplicate_rule"],
            "component_algorithm": "DETERMINISTIC_TRANSITIVE_UNION_FIND",
            "holdout_collision_policy": "ROUTE_HOLDOUT_MEMBER_OUT_OF_INDEPENDENT_HOLDOUT",
            "group_claim_limit": "Exclusion-control identifiers only; not real-world case findings.",
        },
        "output": {"path": str(output_path.resolve())},
        "decision": {
            "offline_grouping_allowed_after_release_qa": True,
            "network_access_allowed": False,
            "human_label_review_allowed": False,
            "model_scoring_allowed": False,
            "validation_or_test_opening_allowed": False,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--text-qa", type=Path, required=True)
    parser.add_argument("--opened-index", type=Path, required=True)
    parser.add_argument("--legacy-remediation", type=Path, required=True)
    parser.add_argument("--analysis-output", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite grouping V2 release")
    release = build_release(
        manifest_path=args.manifest, text_qa_path=args.text_qa,
        opened_index_path=args.opened_index, legacy_remediation_path=args.legacy_remediation,
        output_path=args.analysis_output, created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"release_id": RELEASE_ID, "output": str(args.output), "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
