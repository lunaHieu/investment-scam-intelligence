"""Build a balanced blinded English second-review packet for Wayback holdout V3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_wayback_language_second_review_v2 import build_blind_packet, write_jsonl
from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def build_v3_blind_packet(
    primary_packet: dict[str, object],
    primary_review: dict[str, object],
    *,
    seed: str,
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, int]]:
    packet, mappings, counts = build_blind_packet(primary_packet, primary_review, seed=seed)
    packet["packet_id"] = "EXTERNAL_TEXT_WAYBACK_HOLDOUT_BLIND_SECOND_REVIEW_V3"
    for item in packet["items"]:
        item["blind_review_id"] = str(item["blind_review_id"]).replace("WB2BR_", "WB3BR_", 1)
    for row in mappings:
        row["blind_review_id"] = str(row["blind_review_id"]).replace("WB2BR_", "WB3BR_", 1)
    packet["items"].sort(key=lambda row: str(row["blind_review_id"]))
    mappings.sort(key=lambda row: str(row["blind_review_id"]))
    if any(not str(item["blind_review_id"]).startswith("WB3BR_") for item in packet["items"]):
        raise ValueError("Unexpected V3 blind-review ID")
    return packet, mappings, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--primary-packet", type=Path, required=True)
    parser.add_argument("--primary-packet-sha256", required=True)
    parser.add_argument("--primary-review", type=Path, required=True)
    parser.add_argument("--primary-review-sha256", required=True)
    parser.add_argument("--seed", default="20261002-wayback-holdout-blind-second-review-v3")
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
    primary_packet = load_json(args.primary_packet)
    primary_review = load_json(args.primary_review)
    if primary_packet.get("packet_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_PRIMARY_REVIEW_V3":
        raise ValueError("Unexpected V3 primary-review packet ID")
    if primary_review.get("review_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_AI_PRIMARY_REVIEW_V3":
        raise ValueError("Unexpected V3 primary-review record ID")
    packet, mappings, counts = build_v3_blind_packet(primary_packet, primary_review, seed=args.seed)
    args.packet.parent.mkdir(parents=True, exist_ok=True)
    args.packet.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.mapping.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.mapping, mappings)
    report = {
        "analysis_id": "EXTERNAL_TEXT_WAYBACK_HOLDOUT_SECOND_REVIEW_PREPARATION_V3",
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
