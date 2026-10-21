"""Build the blinded captured-subset second-review packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.build_sec_edgar_iapd_blind_second_review_packet_v1 as frozen_v1
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


PRIMARY_QA_STATUS = "PASS_CAPTURED_SUBSET_PRIMARY_REVIEW_BLIND_SECOND_REVIEW_MAY_BE_PREPARED"


def build(primary_packet_path: Path, primary_review_path: Path, primary_qa_path: Path) -> dict[str, Any]:
    original_status = frozen_v1.PRIMARY_QA_STATUS
    frozen_v1.PRIMARY_QA_STATUS = PRIMARY_QA_STATUS
    try:
        packet = frozen_v1.build(primary_packet_path, primary_review_path, primary_qa_path)
    finally:
        frozen_v1.PRIMARY_QA_STATUS = original_status
    packet["packet_id"] = "ISI_SEC_EDGAR_IAPD_BLIND_SECOND_REVIEW_PACKET_V2"
    packet["population_contract"] = {
        "source_capture_plan_rows": 58,
        "captured_subset_rows": 57,
        "blind_second_review_rows": 56,
        "below_minimum_rows": 1,
        "capture_quarantined_rows": 1,
    }
    serialized = json.dumps(packet, ensure_ascii=False)
    for forbidden in ('"primary_recommendation":', '"primary_assessments":', '"primary_rationale":', '"recommendation_counts":'):
        if forbidden in serialized:
            raise ValueError(f"Blind V2 packet leaked primary decision material: {forbidden}")
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-packet", type=Path, required=True)
    parser.add_argument("--primary-review", type=Path, required=True)
    parser.add_argument("--primary-qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite blind second-review V2 packet")
    packet = build(args.primary_packet, args.primary_review, args.primary_qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"packet_id": packet["packet_id"], "record_count": packet["record_count"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
