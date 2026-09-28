"""Reconcile matched Wayback first/second reviews without scoring a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from validate_external_text_intake import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def reconcile(
    candidates: list[dict], mappings: list[dict], second_reviews: list[dict], seed: str
) -> tuple[list[dict], list[dict], dict[str, int]]:
    candidate_by_id = {item["candidate_id"]: item for item in candidates}
    mapping_by_blind = {item["blind_review_id"]: item for item in mappings}
    review_by_blind = {item["blind_review_id"]: item for item in second_reviews}
    if len(mapping_by_blind) != len(mappings) or set(mapping_by_blind) != set(review_by_blind):
        raise ValueError("Mapping and second-review IDs do not align")
    agreements = []
    nonagreements = []
    for review_id in sorted(mapping_by_blind):
        mapping = mapping_by_blind[review_id]
        review = review_by_blind[review_id]
        candidate = candidate_by_id.get(mapping["candidate_id"])
        if candidate is None:
            raise ValueError(f"Mapped candidate is missing: {review_id}")
        if (
            candidate["artifact"]["text_sha256"] != mapping["artifact_text_sha256"]
            or candidate["artifact"]["source_capture_sha256"] != mapping["capture_sha256"]
        ):
            raise ValueError(f"Mapped artifact hash mismatch: {review_id}")
        agrees = (
            review["decision"] == mapping["reference_status"]
            and review["confidence"] == "HIGH"
        )
        summary = {
            "blind_review_id": review_id,
            "candidate_id": mapping["candidate_id"],
            "first_review_status": mapping["reference_status"],
            "second_review_decision": review["decision"],
            "second_review_confidence": review["confidence"],
            "agreement": agrees,
        }
        if agrees:
            agreements.append((candidate, mapping, review))
        else:
            nonagreements.append(summary)
    grouped = {
        status: [item for item in agreements if item[1]["reference_status"] == status]
        for status in ("CONFIRMED", "LEGITIMATE")
    }
    matched_count = min(len(grouped["CONFIRMED"]), len(grouped["LEGITIMATE"]))
    selected = []
    for status in ("CONFIRMED", "LEGITIMATE"):
        grouped[status].sort(
            key=lambda item: hashlib.sha256(
                f"{seed}|{item[1]['candidate_id']}".encode("utf-8")
            ).hexdigest()
        )
        selected.extend(grouped[status][:matched_count])
    records = []
    for index, (candidate, mapping, review) in enumerate(
        sorted(selected, key=lambda item: item[1]["blind_review_id"]), start=1
    ):
        records.append(
            {
                "benchmark_record_id": f"MWB1_{index:03d}",
                "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
                "ground_truth_status": mapping["reference_status"],
                "label_confidence": "HIGH",
                "review_status": "AI_FIRST_AND_INDEPENDENT_BLINDED_AI_SECOND_REVIEW_AGREEMENT",
                "artifact": candidate["artifact"],
                "evidence": candidate["evidence"],
                "review_provenance": {
                    "source_candidate_id": mapping["candidate_id"],
                    "first_review_status": mapping["reference_status"],
                    "second_review_id": review["blind_review_id"],
                    "second_review_decision": review["decision"],
                    "second_review_confidence": review["confidence"],
                    "second_review_rationale": review["rationale"],
                    "independent_ai_second_review": True,
                    "independent_human_second_review": False,
                },
                "external_evaluation_eligible_after_owner_acceptance": True,
                "training_eligible": False,
            }
        )
    counts = {
        "confirmed_agreements": len(grouped["CONFIRMED"]),
        "legitimate_agreements": len(grouped["LEGITIMATE"]),
        "matched_per_class": matched_count,
        "materialized_records": len(records),
    }
    return records, nonagreements, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--second-review", type=Path, required=True)
    parser.add_argument("--reserve-mapping", type=Path)
    parser.add_argument("--reserve-second-review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    config = load_json(args.config)
    second_review = load_json(args.second_review)
    mappings = load_jsonl(args.mapping)
    reviews = list(second_review.get("reviews", []))
    if bool(args.reserve_mapping) != bool(args.reserve_second_review):
        raise ValueError("Reserve mapping and reserve second review must be supplied together")
    reserve_review = None
    if args.reserve_mapping:
        reserve_review = load_json(args.reserve_second_review)
        mappings.extend(load_jsonl(args.reserve_mapping))
        reviews.extend(reserve_review.get("reviews", []))
    records, nonagreements, counts = reconcile(
        load_jsonl(args.candidates), mappings, reviews, str(config["selection_seed"])
    )
    benchmark = {
        "benchmark_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_BENCHMARK_V1",
        "status": "OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING",
        "capture_strata": ["WAYBACK_ARCHIVED_HOMEPAGE_HTML"],
        "records": records,
        "review_contract": {
            "independent_ai_second_review_complete": True,
            "independent_human_second_review_complete": False,
            "model_outputs_used_during_review": False,
            "agreement_required": True,
        },
    }
    report = {
        "analysis_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_RECONCILIATION_V1",
        "status": "MATCHED_REVIEWED_BENCHMARK_MATERIALIZED_OWNER_ACCEPTANCE_REQUIRED",
        "inputs": {
            "config": {"path": str(args.config), "sha256": sha256_file(args.config)},
            "candidates": {"path": str(args.candidates), "sha256": sha256_file(args.candidates)},
            "mapping": {"path": str(args.mapping), "sha256": sha256_file(args.mapping)},
            "second_review": {"path": str(args.second_review), "sha256": sha256_file(args.second_review)},
            "reserve_mapping": (
                {"path": str(args.reserve_mapping), "sha256": sha256_file(args.reserve_mapping)}
                if args.reserve_mapping
                else None
            ),
            "reserve_second_review": (
                {"path": str(args.reserve_second_review), "sha256": sha256_file(args.reserve_second_review)}
                if args.reserve_second_review
                else None
            ),
        },
        "counts": counts,
        "nonagreements": nonagreements,
        "gates": {
            "capture_stratum_contains_both_classes": counts["matched_per_class"] > 0,
            "class_counts_balanced": counts["materialized_records"] == 2 * counts["matched_per_class"],
            "second_review_complete": True,
            "owner_acceptance_complete": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "independent_human_review_claimed": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(benchmark, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["output"] = {"path": str(args.output), "sha256": sha256_file(args.output)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
