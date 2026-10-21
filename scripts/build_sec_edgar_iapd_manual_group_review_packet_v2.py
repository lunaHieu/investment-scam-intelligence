"""Build the bounded V2 manual group-review packet for the captured subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.build_sec_edgar_iapd_manual_group_review_packet_v1 as frozen_v1
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


GROUPING_QA_STATUS = "PASS_CAPTURED_SUBSET_GROUPING_REPRODUCED_MANUAL_GROUP_REVIEW_MAY_BE_PREPARED"


def build(grouping_path: Path, grouping_qa_path: Path, manifest_path: Path) -> dict[str, Any]:
    original_status = frozen_v1.GROUPING_QA_STATUS
    frozen_v1.GROUPING_QA_STATUS = GROUPING_QA_STATUS
    try:
        packet = frozen_v1.build(grouping_path, grouping_qa_path, manifest_path)
    finally:
        frozen_v1.GROUPING_QA_STATUS = original_status
    packet["packet_id"] = "ISI_SEC_EDGAR_IAPD_MANUAL_GROUP_REVIEW_PACKET_V2"
    packet["population_contract"] = {
        "source_capture_plan_rows": 58,
        "captured_subset_rows": 57,
        "reviewable_rows": 56,
        "below_minimum_rows": 1,
        "capture_quarantined_rows": 1,
        "ordered_capture_quarantine_ids": ["TTCV1_EDGAR_AVAIL_DEV_037"],
    }
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouping", type=Path, required=True)
    parser.add_argument("--grouping-qa", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite manual group-review V2 packet")
    packet = build(args.grouping, args.grouping_qa, args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"packet_id": packet["packet_id"], "record_count": packet["record_count"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
