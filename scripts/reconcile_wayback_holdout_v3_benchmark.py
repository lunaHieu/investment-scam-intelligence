"""Reconcile V3 reviews and freeze a balanced English external holdout benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reconcile_wayback_language_benchmark_v2 import reconcile
from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--primary-packet", type=Path, required=True)
    parser.add_argument("--primary-packet-sha256", required=True)
    parser.add_argument("--primary-review", type=Path, required=True)
    parser.add_argument("--primary-review-sha256", required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--mapping-sha256", required=True)
    parser.add_argument("--second-review", type=Path, required=True)
    parser.add_argument("--second-review-sha256", required=True)
    parser.add_argument("--seed", default="20261002-wayback-holdout-benchmark-v3")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    inputs = (
        (args.config, args.config_sha256),
        (args.primary_packet, args.primary_packet_sha256),
        (args.primary_review, args.primary_review_sha256),
        (args.mapping, args.mapping_sha256),
        (args.second_review, args.second_review_sha256),
    )
    for path, expected in inputs:
        if sha256_file(path) != expected:
            raise ValueError(f"Input SHA-256 mismatch: {path}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    minimum = int(config["language_stratification"]["minimum_dual_review_agreements_per_class"]["ENGLISH"])
    primary_packet = json.loads(args.primary_packet.read_text(encoding="utf-8"))
    primary_review = json.loads(args.primary_review.read_text(encoding="utf-8"))
    second_review = json.loads(args.second_review.read_text(encoding="utf-8"))
    if primary_packet.get("packet_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_PRIMARY_REVIEW_V3":
        raise ValueError("Unexpected V3 primary packet")
    if second_review.get("review_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_INDEPENDENT_SECOND_REVIEW_V3":
        raise ValueError("Unexpected V3 second-review record")
    records, nonagreements, counts = reconcile(
        primary_packet,
        primary_review,
        load_jsonl(args.mapping),
        second_review,
        seed=args.seed,
    )
    for index, record in enumerate(records, start=1):
        record["benchmark_record_id"] = f"WBH3_EN_{index:03d}"
    gate_open = counts["matched_per_class"] >= minimum
    benchmark = {
        "benchmark_id": "EXTERNAL_TEXT_WAYBACK_HOLDOUT_BENCHMARK_V3",
        "status": "OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING" if gate_open else "ENGLISH_STRATUM_MINIMUM_NOT_MET",
        "records": records if gate_open else [],
        "model_input_contract": {
            "allowed_input": "artifact.visible_text only",
            "warning_or_registry_evidence_as_model_input_allowed": False,
            "review_rationale_as_model_input_allowed": False,
        },
        "review_contract": {
            "ai_primary_review_complete": True,
            "independent_blinded_ai_second_review_complete": True,
            "independent_human_second_review_complete": False,
            "high_confidence_agreement_required": True,
        },
        "training_eligible": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(benchmark, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    language_counts = primary_review.get("counts", {}).get("language_decisions", {})
    report = {
        "analysis_id": "EXTERNAL_TEXT_WAYBACK_HOLDOUT_RECONCILIATION_V3",
        "status": "BALANCED_ENGLISH_HOLDOUT_FROZEN_OWNER_ACCEPTANCE_REQUIRED" if gate_open else "ENGLISH_STRATUM_MINIMUM_NOT_MET",
        "inputs": {path.name: {"path": str(path), "sha256": expected} for path, expected in inputs},
        "selection_seed": args.seed,
        "minimum_dual_review_agreements_per_class": minimum,
        "counts": {**counts, "primary_language_decisions": language_counts},
        "nonagreements": nonagreements,
        "undersized_language_reserve": {
            "NON_ENGLISH": int(language_counts.get("NON_ENGLISH", 0)),
            "action": "PRESERVE_AS_RESERVE_DO_NOT_SCORE",
        },
        "gates": {
            "english_stratum_minimum_met": gate_open,
            "class_counts_balanced": gate_open and counts["materialized_records"] == 2 * counts["matched_per_class"],
            "owner_acceptance_complete": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
        "output": {"path": str(args.output), "sha256": sha256_file(args.output)},
        "safety_contract": {
            "network_operations": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "independent_human_review_claimed": False,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
