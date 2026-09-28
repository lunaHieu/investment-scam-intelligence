"""Build a blinded reserve second-review packet from unused eligible legitimate candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from prepare_matched_wayback_second_review import (
    assert_blind_packet,
    build_blind_item,
    load_json,
    load_jsonl,
    write_jsonl,
)
from validate_external_text_intake import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--primary-mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = {
        "packet": args.output_dir / "blind_second_review_reserve_packet_v1.json",
        "mapping": args.output_dir / "blind_second_review_reserve_mapping_v1.jsonl",
        "report": args.output_dir / "reserve_preparation_report_v1.json",
    }
    if any(path.exists() for path in outputs.values()):
        raise FileExistsError("Refusing to overwrite a frozen reserve-review output")
    config = load_json(args.config)
    selected_ids = {item["candidate_id"] for item in load_jsonl(args.primary_mapping)}
    reserve = [
        item
        for item in load_jsonl(args.candidates)
        if item.get("reference_status") == "LEGITIMATE"
        and item.get("eligible_for_blind_second_review") is True
        and item["candidate_id"] not in selected_ids
    ]
    reserve.sort(key=lambda item: item["candidate_id"])
    if len(reserve) != 5:
        raise ValueError(f"Expected five unused eligible legitimate reserves, found {len(reserve)}")
    blind_items = []
    mappings = []
    for candidate in reserve:
        blind, mapping = build_blind_item(candidate, str(config["selection_seed"]))
        blind_items.append(blind)
        mappings.append(mapping)
    blind_items.sort(key=lambda item: item["blind_review_id"])
    mappings.sort(key=lambda item: item["blind_review_id"])
    packet = {
        "packet_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_BLIND_SECOND_REVIEW_RESERVE_V1",
        "status": "PENDING_INDEPENDENT_SECOND_REVIEW",
        "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
        "blinding": {
            "first_review_decisions_removed": True,
            "model_outputs_removed": True,
            "original_case_ids_removed": True,
            "evidence_sources_visible": True,
        },
        "instructions": [
            "Assess each archived artifact and evidence without consulting first-review, primary-packet, mapping, or model outputs.",
            "LEGITIMATE requires identity/domain alignment with the registration reference and no unresolved impersonation or adverse-evidence conflict.",
            "Use UNCERTAIN or REJECT_CAPTURE whenever evidence or capture quality is insufficient.",
        ],
        "items": blind_items,
    }
    assert_blind_packet(packet)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs["packet"].write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_jsonl(outputs["mapping"], mappings)
    report = {
        "analysis_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_SECOND_REVIEW_RESERVE_PREPARATION_V1",
        "status": "BLIND_RESERVE_SECOND_REVIEW_READY",
        "reserve_count": len(reserve),
        "outputs": {
            "packet": {"path": str(outputs["packet"]), "sha256": sha256_file(outputs["packet"])},
            "mapping": {"path": str(outputs["mapping"]), "sha256": sha256_file(outputs["mapping"])},
        },
        "safety_contract": {
            "labels_exposed_to_reviewer": False,
            "model_outputs_exposed_to_reviewer": False,
            "labels_created": 0,
            "training_allowed": False,
        },
    }
    outputs["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
