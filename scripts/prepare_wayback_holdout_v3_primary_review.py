"""Freeze the Wayback holdout V3 primary-review packet without scoring a model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_wayback_language_primary_review_v2 import build_primary_packet, write_jsonl
from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--queue-sha256", required=True)
    parser.add_argument("--screening", type=Path, required=True)
    parser.add_argument("--screening-sha256", required=True)
    parser.add_argument("--reference-index", nargs=2, action="append", metavar=("PATH", "SHA256"), required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.packet, args.mapping, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    for path, expected in (
        (args.config, args.config_sha256),
        (args.queue, args.queue_sha256),
        (args.screening, args.screening_sha256),
    ):
        if sha256_file(path) != expected:
            raise ValueError(f"Input SHA-256 mismatch: {path}")
    reference_inputs = [(Path(path), expected) for path, expected in args.reference_index]
    rows_by_key = {}
    for path, expected in reference_inputs:
        if sha256_file(path) != expected:
            raise ValueError(f"Reference index SHA-256 mismatch: {path}")
        for row in load_jsonl(path):
            key = (str(row["source_id"]), str(row["source_record_id"]))
            if key in rows_by_key:
                raise ValueError(f"Duplicate official reference key: {key}")
            rows_by_key[key] = row
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("protocol_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_V3":
        raise ValueError("Unexpected V3 protocol")
    packet, mappings = build_primary_packet(
        load_jsonl(args.queue), load_jsonl(args.screening), rows_by_key
    )
    packet["packet_id"] = "EXTERNAL_TEXT_WAYBACK_HOLDOUT_PRIMARY_REVIEW_V3"
    packet["instructions"].append(
        "These candidates are a fresh holdout: do not consult any existing model output or the opened V2 benchmark."
    )
    args.packet.parent.mkdir(parents=True, exist_ok=True)
    args.packet.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_jsonl(args.mapping, mappings)
    branch_counts = {}
    for row in mappings:
        branch = str(row["reference_branch"])
        branch_counts[branch] = branch_counts.get(branch, 0) + 1
    report = {
        "analysis_id": "EXTERNAL_TEXT_WAYBACK_HOLDOUT_PRIMARY_REVIEW_PREPARATION_V3",
        "status": "AI_PRIMARY_REVIEW_PACKET_READY_NOT_HUMAN",
        "inputs": {
            "config": {"path": str(args.config), "sha256": args.config_sha256},
            "queue": {"path": str(args.queue), "sha256": args.queue_sha256},
            "screening": {"path": str(args.screening), "sha256": args.screening_sha256},
            "reference_indices": [
                {"path": str(path), "sha256": expected} for path, expected in reference_inputs
            ],
        },
        "counts": {"review_items": len(packet["items"]), "by_reference_branch": branch_counts},
        "outputs": {
            "packet": {"path": str(args.packet), "sha256": sha256_file(args.packet)},
            "mapping": {"path": str(args.mapping), "sha256": sha256_file(args.mapping)},
        },
        "safety_contract": {
            "network_operations": 0,
            "model_scoring_operations": 0,
            "labels_created": 0,
            "independent_human_review_claimed": False,
            "training_allowed": False,
        },
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
