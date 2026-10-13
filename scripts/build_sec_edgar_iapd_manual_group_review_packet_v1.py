"""Build a bounded, label-free manual group-review packet for SEC/IAPD rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


GROUPING_QA_STATUS = "PASS_GROUPING_REPRODUCED_MANUAL_GROUP_REVIEW_MAY_BE_PREPARED"
EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d() .-]{6,}\d)(?!\w)")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(grouping_path: Path, grouping_qa_path: Path, manifest_path: Path) -> dict[str, Any]:
    grouping = load_object(grouping_path)
    grouping_qa = load_object(grouping_qa_path)
    if grouping_qa.get("status") != GROUPING_QA_STATUS:
        raise ValueError("Grouping QA did not release manual-review preparation")
    if grouping_qa.get("inputs", {}).get("analysis_sha256") != sha256_file(grouping_path):
        raise ValueError("Grouping QA/analysis hash mismatch")
    if grouping_qa.get("decision", {}).get("manual_group_review_may_be_prepared") is not True:
        raise PermissionError("Manual group-review preparation gate is closed")
    manifest = {row["record_id"]: row for row in read_jsonl(manifest_path)}
    grouping_rows = list(grouping.get("records", []))
    if set(manifest) != {row["record_id"] for row in grouping_rows}:
        raise ValueError("Grouping/manifest membership mismatch")
    records = []
    for grouped in grouping_rows:
        if not grouped["minimum_content_passed"]:
            continue
        record_id = grouped["record_id"]
        text_row = manifest[record_id]
        text_path = Path(text_row["text_path"])
        payload = text_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != text_row["text_sha256"]:
            raise ValueError(f"Exact text changed: {record_id}")
        text = payload.decode("utf-8")
        records.append({
            "record_id": record_id,
            "shortlist_id": grouped["shortlist_id"],
            "cohort": grouped["cohort"],
            "candidate_host": grouped["candidate_host"],
            "artifact": {
                "text_path": str(text_path),
                "text_sha256": text_row["text_sha256"],
                "visible_text_characters": text_row["visible_text_characters"],
                "canonical_urls_declared_in_capture": text_row["canonical_urls_declared_in_capture"],
                "contact_email_indicators": sorted({value.rstrip(".,;:)").casefold() for value in EMAIL.findall(text)}),
                "contact_phone_indicators": sorted({re.sub(r"\s+", " ", value).strip(" .") for value in PHONE.findall(text)}),
            },
            "automated_screen": {
                "routing_decision": grouped["routing_decision"],
                "opened_overlap": grouped["opened_overlap"],
                "candidate_internal_near_duplicate_hits": grouped["candidate_internal_near_duplicate_hits"],
                "technical_group": grouped["technical_group"],
                "cross_cohort_group_collision": grouped["cross_cohort_group_collision"],
            },
            "review_form": {
                "group_decision": "PENDING_MANUAL_REVIEW",
                "linked_record_ids": [],
                "canonical_record_id": None,
                "linked_opened_record_keys": [],
                "positive_linkage_evidence": [],
                "identity_or_content_flags_for_primary_review": [],
                "rationale": None,
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            },
        })
    return {
        "packet_id": "ISI_SEC_EDGAR_IAPD_MANUAL_GROUP_REVIEW_PACKET_V1",
        "status": "FROZEN_UNREVIEWED_PACKET",
        "inputs": {
            "grouping_analysis": {"path": str(grouping_path.resolve()), "sha256": sha256_file(grouping_path)},
            "grouping_qa": {"path": str(grouping_qa_path.resolve()), "sha256": sha256_file(grouping_qa_path)},
            "exact_text_manifest": {"path": str(manifest_path.resolve()), "sha256": sha256_file(manifest_path)},
        },
        "review_scope": {
            "question": "Do positive local evidence and captured text require merging, opened-clone routing, or confirmation of an automated exclusion?",
            "allowed_decisions": ["KEEP_PROVISIONALLY_DISTINCT", "MERGE_TECHNICAL_GROUPS", "ROUTE_OPENED_COHORT_CLONE_REVIEW", "CONFIRM_AUTOMATED_EXCLUSION", "UNRESOLVED_GROUP_RELATIONSHIP"],
            "forbidden_inferences": ["SEC_OR_IAPD_MEMBERSHIP_IS_A_LABEL", "MODEL_PREDICTION_IS_EVIDENCE", "GENERIC_FINANCE_LANGUAGE_PROVES_COMMON_CONTROL"],
            "labeling_allowed": False,
        },
        "record_count": len(records),
        "records": records,
        "safety_contract": {"network_operations": 0, "model_predictions_visible": False, "labels_created": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouping", type=Path, required=True)
    parser.add_argument("--grouping-qa", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite manual group-review packet")
    packet = build(args.grouping, args.grouping_qa, args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"packet_id": packet["packet_id"], "record_count": packet["record_count"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
