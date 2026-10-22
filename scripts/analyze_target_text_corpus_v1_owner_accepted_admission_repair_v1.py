"""Audit admission-repair readiness for the exact 42 owner-accepted records."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_OWNER_ACCEPTED_ADMISSION_REPAIR_PROTOCOL_V1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_protocol(config_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    config = load_object(config_path)
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        raise ValueError("Unexpected admission-repair protocol")
    root = config_path.resolve().parents[1]
    paths: dict[str, Path] = {}
    for item in config["inputs"]:
        path = _resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Admission-repair input mismatch: {item['role']}")
        paths[item["role"]] = path

    blockers = config["blocker_contract"]
    declared = set(blockers["audit_blockers"])
    classified = {
        item["audit_blocker"]
        for section in ("human_review_now", "offline_evidence_packet_now_but_no_admission_credit", "full_channel_or_population_only")
        for item in blockers[section]
    }
    if len(declared) != 9 or declared != classified:
        raise ValueError("The nine admission blockers are not classified exactly once")
    if config["evidence_reuse_contract"].get("technical_group_may_be_renamed_as_semantic_group") is not False:
        raise PermissionError("Protocol permits unsupported semantic group promotion")
    for gate in (
        "repaired_candidate_manifest_allowed", "partial_channel_contribution_allowed", "network_access_allowed",
        "candidate_domain_access_allowed", "labeling_allowed", "validation_or_test_opening_allowed",
        "model_scoring_allowed", "training_allowed",
    ):
        if config["decision"].get(gate) is not False:
            raise PermissionError(f"Admission-repair protocol opened forbidden gate: {gate}")
    return config, paths


def analyze(config_path: Path) -> dict[str, Any]:
    config, paths = validate_protocol(config_path)
    owner = load_object(paths["owner_accepted_records"])
    owner_rows = list(owner.get("records", []))
    ids = [str(row.get("record_id", "")) for row in owner_rows]
    population = config["population_contract"]
    digest = hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    if len(ids) != population["record_count"] or len(ids) != len(set(ids)) or digest != population["ordered_record_ids_sha256"]:
        raise ValueError("Owner-accepted population identity changed")
    counts = Counter(str(row.get("cohort")) for row in owner_rows)
    if counts != {"DEVELOPMENT": population["development_count"], "EXTERNAL_HOLDOUT": population["external_holdout_count"]}:
        raise ValueError("Owner-accepted cohort counts changed")
    if any(row.get("ground_truth_status") != population["target_status"] or row.get("label_created") is not True for row in owner_rows):
        raise ValueError("Owner-accepted label state changed")
    for row in owner_rows:
        expected_training = "NO_PENDING_BALANCED_DATASET_RELEASE" if row["cohort"] == "DEVELOPMENT" else "NO_EXTERNAL_HOLDOUT"
        expected_scoring = "NO" if row["cohort"] == "DEVELOPMENT" else "NO_PENDING_FROZEN_EVALUATION_RELEASE"
        if row.get("training_eligible") != expected_training or row.get("model_scoring_eligible") != expected_scoring:
            raise PermissionError("Owner-accepted record became training or scoring eligible")

    exact = {str(row["record_id"]): row for row in _read_jsonl(paths["exact_text_manifest"])}
    grouping_data = load_object(paths["post_capture_grouping"])
    grouping = {str(row["record_id"]): row for row in grouping_data["records"]}
    manual_data = load_object(paths["manual_group_review"])
    manual = {str(row["record_id"]): row for row in manual_data["records"]}
    if any(record_id not in exact or record_id not in grouping or record_id not in manual for record_id in ids):
        raise ValueError("An accepted record is missing frozen text or grouping evidence")
    for record_id in ids:
        text_row = exact[record_id]
        group_row = grouping[record_id]
        manual_row = manual[record_id]
        if text_row.get("minimum_content_passed") is not True or group_row.get("minimum_content_passed") is not True:
            raise ValueError(f"Accepted record failed minimum text gate: {record_id}")
        if text_row.get("text_sha256") != group_row.get("text_sha256") or text_row.get("raw_capture_sha256") != group_row.get("raw_capture_sha256"):
            raise ValueError(f"Accepted record text/capture evidence mismatch: {record_id}")
        opened_overlap = group_row.get("opened_overlap")
        opened_clear = isinstance(opened_overlap, dict) and all(not values for values in opened_overlap.values())
        if not opened_clear or group_row.get("cross_cohort_group_collision") is not False:
            raise ValueError(f"Accepted record has exclusion collision: {record_id}")
        if manual_row.get("group_decision") != "KEEP_PROVISIONALLY_DISTINCT":
            raise ValueError(f"Unexpected provisional group decision: {record_id}")

    return {
        "report_id": config["planned_output"]["report_id"],
        "status": "PASS_EXACT_42_READINESS_AUDITED_ZERO_FIELDS_PREMATURELY_CREDITED",
        "protocol": {"path": str(config_path.resolve()), "sha256": sha256_file(config_path)},
        "population": {
            "ordered_record_ids_sha256": digest,
            "record_count": len(ids),
            "development_count": counts["DEVELOPMENT"],
            "external_holdout_count": counts["EXTERNAL_HOLDOUT"],
            "target_status": population["target_status"],
            "channel_id": population["channel_id"],
        },
        "evidence_coverage": {
            "owner_accepted_label_provenance": len(ids),
            "minimum_text_and_hash_chain": len(ids),
            "opened_and_cross_cohort_exclusion_at_current_population": len(ids),
            "provisional_manual_group_review": len(ids),
        },
        "blocker_disposition": {
            "human_review_now": {"blocker_count": 1, "record_count": len(ids), "admission_credit_now": 0},
            "offline_evidence_packet_now_but_no_admission_credit": {"blocker_count": 1, "record_count": len(ids), "admission_credit_now": 0},
            "full_channel_or_population_only": {"blocker_count": 7, "record_count": len(ids), "admission_credit_now": 0},
        },
        "decision": {
            "protocol_qa_ready": True,
            "language_review_packet_may_be_prepared": True,
            "fresh_cohort_assertion_packet_may_be_prepared": True,
            "repaired_candidate_manifest_created": False,
            "channel_contribution_created": False,
            "v1_core_admitted_records": 0,
            "training_allowed": False,
            "next_gate": "Prepare separate hash-bound language-review and fresh-cohort assertion packets for the exact 42 records; retain all release-wide fields as blocked.",
        },
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "labels_changed": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = analyze(args.config)
    if args.verify_only:
        print(json.dumps({"status": result["status"], "population": result["population"], "decision": result["decision"]}, ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        raise ValueError("--output is required unless --verify-only is used")
    expected = Path(load_object(args.config)["planned_output"]["path"])
    if args.output.resolve() != expected.resolve():
        raise ValueError("Output path differs from frozen protocol")
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite admission-repair readiness output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"status": result["status"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
