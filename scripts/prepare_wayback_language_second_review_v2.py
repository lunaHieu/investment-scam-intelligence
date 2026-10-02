"""Build a balanced blinded English second-review packet for Wayback language V2."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def stable_key(seed: str, candidate_id: str) -> str:
    return hashlib.sha256(f"{seed}|{candidate_id}".encode("utf-8")).hexdigest()


def build_blind_packet(
    primary_packet: dict[str, object],
    primary_review: dict[str, object],
    *,
    seed: str,
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, int]]:
    packet_items = {str(item["candidate_id"]): item for item in primary_packet["items"]}
    eligible: dict[str, list[dict[str, object]]] = {"CONFIRMED": [], "LEGITIMATE": []}
    for review in primary_review["reviews"]:
        decision = str(review["evidence_decision"])
        if (
            decision in eligible
            and review["confidence"] == "HIGH"
            and review["language_decision"] == "ENGLISH"
        ):
            eligible[decision].append(review)
    matched = min(len(eligible["CONFIRMED"]), len(eligible["LEGITIMATE"]))
    if matched < 1:
        raise ValueError("No balanced English primary-review agreements are available")
    selected: list[dict[str, object]] = []
    for decision in ("CONFIRMED", "LEGITIMATE"):
        eligible[decision].sort(key=lambda row: stable_key(seed, str(row["candidate_id"])))
        selected.extend(eligible[decision][:matched])
    blind_items: list[dict[str, object]] = []
    mappings: list[dict[str, object]] = []
    for review in selected:
        candidate_id = str(review["candidate_id"])
        item = packet_items.get(candidate_id)
        if item is None:
            raise ValueError(f"Primary packet item is absent: {candidate_id}")
        if (
            review["artifact_text_sha256"] != item["artifact"]["text_sha256"]
            or review["capture_sha256"] != item["artifact"]["capture_sha256"]
        ):
            raise ValueError(f"Primary review artifact hashes do not bind: {candidate_id}")
        review_id = f"WB2BR_{stable_key(seed, candidate_id)[:16].upper()}"
        blind_items.append(
            {
                "blind_review_id": review_id,
                "candidate_host": item["candidate_host"],
                "capture_stratum": item["capture_stratum"],
                "artifact": {
                    "visible_text": item["artifact"]["visible_text"],
                    "text_sha256": item["artifact"]["text_sha256"],
                    "capture_sha256": item["artifact"]["capture_sha256"],
                },
                "official_reference": item["official_reference"],
                "official_reference_record": item["official_reference_record"],
                "entity_name_keys": item["entity_name_keys"],
                "review_contract": {
                    "allowed_decisions": ["CONFIRMED", "LEGITIMATE", "UNCERTAIN", "REJECT_CAPTURE"],
                    "allowed_confidence": ["HIGH", "MEDIUM", "LOW"],
                    "must_reconcile_archived_identity_with_official_reference": True,
                    "must_check_repurpose_or_impersonation_contradictions": True,
                    "must_not_consult_mapping_primary_review_or_model_outputs": True,
                },
            }
        )
        mappings.append(
            {
                "blind_review_id": review_id,
                "candidate_id": candidate_id,
                "first_review_decision": review["evidence_decision"],
                "first_review_confidence": review["confidence"],
                "language_decision": review["language_decision"],
                "artifact_text_sha256": review["artifact_text_sha256"],
                "capture_sha256": review["capture_sha256"],
            }
        )
    blind_items.sort(key=lambda row: str(row["blind_review_id"]))
    mappings.sort(key=lambda row: str(row["blind_review_id"]))
    packet = {
        "packet_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_BLIND_SECOND_REVIEW_V2",
        "status": "PENDING_INDEPENDENT_BLINDED_AI_SECOND_REVIEW_NOT_HUMAN",
        "language_stratum": "ENGLISH",
        "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
        "blinding": {
            "candidate_ids_removed": True,
            "source_case_ids_removed": True,
            "reference_branch_removed": True,
            "first_review_removed": True,
            "model_outputs_removed": True,
            "evidence_sources_visible": True,
        },
        "instructions": [
            "Review only this packet; do not open the mapping, primary-review artifacts, configs, registries, model outputs, or prior conversation.",
            "CONFIRMED requires exact identity/domain alignment with an official warning and no unresolved repurpose contradiction.",
            "LEGITIMATE requires exact identity/domain alignment with the registration record and no unresolved impersonation contradiction.",
            "Use UNCERTAIN or REJECT_CAPTURE whenever the evidence or capture is insufficient.",
            "This is independent blinded AI review, not human review.",
        ],
        "items": blind_items,
    }
    prohibited = {"candidate_id", "source_case_id", "reference_branch", "first_review_decision", "model_prediction", "score_label_1"}
    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).casefold() in prohibited:
                    raise ValueError(f"Blind packet leaks prohibited field: {key}")
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(packet)
    counts = {
        "eligible_confirmed_english": len(eligible["CONFIRMED"]),
        "eligible_legitimate_english": len(eligible["LEGITIMATE"]),
        "selected_per_class": matched,
        "selected_total": len(selected),
    }
    return packet, mappings, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--primary-packet", type=Path, required=True)
    parser.add_argument("--primary-packet-sha256", required=True)
    parser.add_argument("--primary-review", type=Path, required=True)
    parser.add_argument("--primary-review-sha256", required=True)
    parser.add_argument("--seed", default="20261001-wayback-language-blind-second-review-v2")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.packet, args.mapping, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    for path, expected in (
        (args.config, args.config_sha256),
        (args.primary_packet, args.primary_packet_sha256),
        (args.primary_review, args.primary_review_sha256),
    ):
        if sha256_file(path) != expected:
            raise ValueError(f"Input SHA-256 mismatch: {path}")
    packet, mappings, counts = build_blind_packet(
        load_json(args.primary_packet), load_json(args.primary_review), seed=args.seed
    )
    args.packet.parent.mkdir(parents=True, exist_ok=True)
    args.packet.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.mapping.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.mapping, mappings)
    report = {
        "analysis_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_SECOND_REVIEW_PREPARATION_V2",
        "status": "BALANCED_BLIND_SECOND_REVIEW_READY",
        "inputs": {
            "config": {"path": str(args.config), "sha256": args.config_sha256},
            "primary_packet": {"path": str(args.primary_packet), "sha256": args.primary_packet_sha256},
            "primary_review": {"path": str(args.primary_review), "sha256": args.primary_review_sha256},
        },
        "selection_seed": args.seed,
        "counts": counts,
        "outputs": {
            "blind_packet": {"path": str(args.packet), "sha256": sha256_file(args.packet)},
            "private_mapping": {"path": str(args.mapping), "sha256": sha256_file(args.mapping)},
        },
        "gates": {
            "balanced_english_packet": counts["selected_per_class"] > 0,
            "second_review_complete": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "model_scoring_operations": 0,
            "independent_human_review_claimed": False,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
