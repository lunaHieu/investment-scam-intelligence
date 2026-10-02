"""Reconcile V2 primary and blinded second reviews and freeze a balanced benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file


def stable_key(seed: str, candidate_id: str) -> str:
    return hashlib.sha256(f"{seed}|{candidate_id}".encode("utf-8")).hexdigest()


def reconcile(
    primary_packet: dict[str, object],
    primary_review: dict[str, object],
    mappings: list[dict[str, object]],
    second_review: dict[str, object],
    *,
    seed: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    packet_by_candidate = {str(item["candidate_id"]): item for item in primary_packet["items"]}
    primary_by_candidate = {str(item["candidate_id"]): item for item in primary_review["reviews"]}
    mapping_by_blind = {str(item["blind_review_id"]): item for item in mappings}
    second_by_blind = {str(item["blind_review_id"]): item for item in second_review["reviews"]}
    if len(mapping_by_blind) != len(mappings) or set(mapping_by_blind) != set(second_by_blind):
        raise ValueError("Private mapping and second-review IDs do not align")
    agreements: dict[str, list[tuple[dict[str, object], dict[str, object], dict[str, object]]]] = {"CONFIRMED": [], "LEGITIMATE": []}
    nonagreements: list[dict[str, object]] = []
    for blind_id in sorted(mapping_by_blind):
        mapping = mapping_by_blind[blind_id]
        candidate_id = str(mapping["candidate_id"])
        primary = primary_by_candidate.get(candidate_id)
        item = packet_by_candidate.get(candidate_id)
        second = second_by_blind[blind_id]
        if primary is None or item is None:
            raise ValueError(f"Mapped primary item is absent: {blind_id}")
        if (
            mapping["artifact_text_sha256"] != item["artifact"]["text_sha256"]
            or mapping["capture_sha256"] != item["artifact"]["capture_sha256"]
            or primary["artifact_text_sha256"] != mapping["artifact_text_sha256"]
            or primary["capture_sha256"] != mapping["capture_sha256"]
        ):
            raise ValueError(f"Artifact hash binding failed: {blind_id}")
        first_decision = str(primary["evidence_decision"])
        agreed = (
            first_decision in agreements
            and mapping["first_review_decision"] == first_decision
            and primary["confidence"] == "HIGH"
            and primary["language_decision"] == "ENGLISH"
            and second["decision"] == first_decision
            and second["confidence"] == "HIGH"
        )
        if agreed:
            agreements[first_decision].append((item, primary, second))
        else:
            nonagreements.append(
                {
                    "blind_review_id": blind_id,
                    "candidate_id": candidate_id,
                    "first_review_decision": first_decision,
                    "first_review_confidence": primary["confidence"],
                    "second_review_decision": second["decision"],
                    "second_review_confidence": second["confidence"],
                }
            )
    matched = min(len(agreements["CONFIRMED"]), len(agreements["LEGITIMATE"]))
    selected = []
    for decision in ("CONFIRMED", "LEGITIMATE"):
        agreements[decision].sort(key=lambda value: stable_key(seed, str(value[0]["candidate_id"])))
        selected.extend(agreements[decision][:matched])
    records: list[dict[str, object]] = []
    for index, (item, primary, second) in enumerate(
        sorted(selected, key=lambda value: stable_key(seed, str(value[0]["candidate_id"]))), start=1
    ):
        records.append(
            {
                "benchmark_record_id": f"WBL2_EN_{index:03d}",
                "language_stratum": "ENGLISH",
                "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
                "ground_truth_status": primary["evidence_decision"],
                "label_confidence": "HIGH",
                "review_status": "AI_PRIMARY_AND_INDEPENDENT_BLINDED_AI_SECOND_REVIEW_AGREEMENT",
                "artifact": {
                    "candidate_host": item["candidate_host"],
                    "visible_text": item["artifact"]["visible_text"],
                    "text_sha256": item["artifact"]["text_sha256"],
                    "capture_sha256": item["artifact"]["capture_sha256"],
                },
                "evidence": {
                    "official_reference": item["official_reference"],
                    "official_reference_record": item["official_reference_record"],
                },
                "review_provenance": {
                    "source_candidate_id": item["candidate_id"],
                    "primary_review_id": primary_review["review_id"],
                    "primary_decision": primary["evidence_decision"],
                    "primary_confidence": primary["confidence"],
                    "second_blind_review_id": second["blind_review_id"],
                    "second_decision": second["decision"],
                    "second_confidence": second["confidence"],
                    "independent_ai_second_review": True,
                    "independent_human_second_review": False,
                },
                "training_eligible": False,
            }
        )
    counts = {
        "confirmed_high_agreements": len(agreements["CONFIRMED"]),
        "legitimate_high_agreements": len(agreements["LEGITIMATE"]),
        "matched_per_class": matched,
        "materialized_records": len(records),
        "nonagreements": len(nonagreements),
    }
    return records, nonagreements, counts


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
    parser.add_argument("--seed", default="20261001-wayback-language-benchmark-v2")
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
    records, nonagreements, counts = reconcile(
        primary_packet,
        primary_review,
        load_jsonl(args.mapping),
        second_review,
        seed=args.seed,
    )
    gate_open = counts["matched_per_class"] >= minimum
    benchmark = {
        "benchmark_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_BENCHMARK_V2",
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
    report = {
        "analysis_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_RECONCILIATION_V2",
        "status": "BALANCED_ENGLISH_BENCHMARK_FROZEN_OWNER_ACCEPTANCE_REQUIRED" if gate_open else "ENGLISH_STRATUM_MINIMUM_NOT_MET",
        "inputs": {path.name: {"path": str(path), "sha256": expected} for path, expected in inputs},
        "selection_seed": args.seed,
        "minimum_dual_review_agreements_per_class": minimum,
        "counts": counts,
        "nonagreements": nonagreements,
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
