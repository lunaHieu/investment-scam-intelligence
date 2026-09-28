"""Screen supplemental SEC/IAPD Wayback captures for a first-review pool."""

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

from prepare_matched_wayback_second_review import build_legitimate_candidate, load_json, load_jsonl, write_jsonl
from validate_external_text_intake import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = {
        "candidates": args.output_dir / "supplement_candidates_v1.jsonl",
        "first_review_packet": args.output_dir / "supplement_first_review_packet_v1.json",
        "report": args.output_dir / "supplement_preparation_report_v1.json",
    }
    if any(path.exists() for path in outputs.values()):
        raise FileExistsError("Refusing to overwrite a frozen supplemental-review output")
    queue = load_jsonl(args.queue)
    capture_report = load_json(args.capture_report)
    capture_items = {
        item["candidate_id"]: item
        for item in capture_report.get("results", [])
        if item.get("outcome") == "CAPTURED"
    }
    candidates = []
    for item in queue:
        capture = capture_items.get(item["candidate_id"])
        if capture is not None:
            candidates.append(build_legitimate_candidate(item, capture, args.raw_root))
    eligible = [item for item in candidates if item["eligible_for_blind_second_review"]]
    packet = {
        "packet_id": "MATCHED_WAYBACK_SUPPLEMENT_FIRST_REVIEW_V1",
        "status": "PENDING_FIRST_REVIEW",
        "model_outputs_included": False,
        "items": [
            {
                "candidate_id": item["candidate_id"],
                "capture_stratum": item["capture_stratum"],
                "artifact": item["artifact"],
                "evidence": item["evidence"],
                "screening": item["screening"],
                "allowed_decisions": ["LEGITIMATE", "UNCERTAIN", "REJECT_CAPTURE"],
                "first_review": {
                    "status": "PENDING",
                    "decision": None,
                    "confidence": None,
                    "rationale": None,
                    "contradictions": [],
                },
            }
            for item in eligible
        ],
    }
    report = {
        "analysis_id": "MATCHED_WAYBACK_SUPPLEMENT_FIRST_REVIEW_PREPARATION_V1",
        "status": "FIRST_REVIEW_READY" if len(eligible) >= 3 else "SUPPLEMENT_GATE_BLOCKED",
        "counts": {
            "queued": len(queue),
            "captured": len(candidates),
            "screening_eligible": len(eligible),
            "screening_rejected": len(candidates) - len(eligible),
            "capture_failed_or_unavailable": len(queue) - len(candidates),
        },
        "screening_rejections": [
            {"candidate_id": item["candidate_id"], "screening": item["screening"]}
            for item in candidates
            if not item["eligible_for_blind_second_review"]
        ],
        "safety_contract": {
            "network_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(outputs["candidates"], candidates)
    outputs["first_review_packet"].write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report["outputs"] = {
        "candidates": {"path": str(outputs["candidates"]), "sha256": sha256_file(outputs["candidates"])},
        "first_review_packet": {
            "path": str(outputs["first_review_packet"]),
            "sha256": sha256_file(outputs["first_review_packet"]),
        },
    }
    outputs["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
