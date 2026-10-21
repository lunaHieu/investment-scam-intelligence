"""Build the captured-subset V2 primary artifact-review packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.build_sec_edgar_iapd_primary_review_packet_v1 as frozen_v1
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


GROUP_REVIEW_QA_STATUS = "PASS_CAPTURED_SUBSET_GROUP_REVIEW_PRIMARY_PACKET_MAY_BE_PREPARED"


def build(
    *, group_packet_path: Path, group_review_path: Path, group_qa_path: Path,
    manifest_path: Path, availability_plan_path: Path,
    offline_review_path: Path, iapd_path: Path,
) -> dict[str, Any]:
    original_status = frozen_v1.GROUP_REVIEW_QA_STATUS
    frozen_v1.GROUP_REVIEW_QA_STATUS = GROUP_REVIEW_QA_STATUS
    try:
        packet = frozen_v1.build(
            group_packet_path=group_packet_path,
            group_review_path=group_review_path,
            group_qa_path=group_qa_path,
            manifest_path=manifest_path,
            availability_plan_path=availability_plan_path,
            offline_review_path=offline_review_path,
            iapd_path=iapd_path,
        )
    finally:
        frozen_v1.GROUP_REVIEW_QA_STATUS = original_status
    packet["packet_id"] = "ISI_SEC_EDGAR_IAPD_PRIMARY_REVIEW_PACKET_V2"
    packet["population_contract"] = {
        "source_capture_plan_rows": 58,
        "captured_subset_rows": 57,
        "primary_review_rows": 56,
        "below_minimum_rows": 1,
        "capture_quarantined_rows": 1,
        "ordered_capture_quarantine_ids": ["TTCV1_EDGAR_AVAIL_DEV_037"],
    }
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group-packet", type=Path, required=True)
    parser.add_argument("--group-review", type=Path, required=True)
    parser.add_argument("--group-qa", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--availability-plan", type=Path, required=True)
    parser.add_argument("--offline-review", type=Path, required=True)
    parser.add_argument("--iapd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite primary-review V2 packet")
    packet = build(
        group_packet_path=args.group_packet, group_review_path=args.group_review,
        group_qa_path=args.group_qa, manifest_path=args.manifest,
        availability_plan_path=args.availability_plan,
        offline_review_path=args.offline_review, iapd_path=args.iapd,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"packet_id": packet["packet_id"], "record_count": packet["record_count"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
