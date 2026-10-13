"""Build the frozen local-evidence packet for SEC/IAPD primary review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


GROUP_REVIEW_QA_STATUS = "PASS_GROUP_REVIEW_PRIMARY_PACKET_MAY_BE_PREPARED"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(
    *, group_packet_path: Path, group_review_path: Path, group_qa_path: Path,
    manifest_path: Path, availability_plan_path: Path,
    offline_review_path: Path, iapd_path: Path,
) -> dict[str, Any]:
    group_packet = load_object(group_packet_path)
    group_review = load_object(group_review_path)
    group_qa = load_object(group_qa_path)
    if group_qa.get("status") != GROUP_REVIEW_QA_STATUS or group_qa.get("decision", {}).get("primary_review_packet_may_be_prepared") is not True:
        raise ValueError("Manual group review did not release primary packet preparation")
    if group_qa.get("inputs", {}).get("packet_sha256") != sha256_file(group_packet_path) or group_qa.get("inputs", {}).get("review_sha256") != sha256_file(group_review_path):
        raise ValueError("Manual group review QA input binding mismatch")
    packet_rows = {row["record_id"]: row for row in group_packet["records"]}
    manifest = {row["record_id"]: row for row in read_jsonl(manifest_path)}
    plan = {row["availability_plan_id"]: row for row in read_jsonl(availability_plan_path)}
    offline = {row["shortlist_id"]: row for row in read_jsonl(offline_review_path)}
    iapd = {str(row["source_record_id"]): row for row in read_jsonl(iapd_path)}
    review_rows = {row["record_id"]: row for row in group_review["records"]}
    if set(review_rows) != set(packet_rows):
        raise ValueError("Group review/packet population mismatch")
    selected: list[str] = []
    for record_id, row in review_rows.items():
        if row["group_decision"] == "KEEP_PROVISIONALLY_DISTINCT":
            selected.append(record_id)
        elif row["group_decision"] == "MERGE_TECHNICAL_GROUPS" and row.get("canonical_record_id") == record_id:
            selected.append(record_id)
    records = []
    for record_id in sorted(selected):
        source = packet_rows[record_id]
        text_row = manifest[record_id]
        plan_row = plan[record_id]
        offline_row = offline[plan_row["shortlist_id"]]
        iapd_row = iapd[str(offline_row["iapd_source_record_id"])]
        text_path = Path(text_row["text_path"])
        if sha256_file(text_path) != text_row["text_sha256"]:
            raise ValueError(f"Exact text changed: {record_id}")
        if iapd_row["normalized_host"] != plan_row["candidate_host"].casefold().rstrip("."):
            raise ValueError(f"IAPD/plan host mismatch: {record_id}")
        if offline_row["cohort"] != plan_row["cohort"] or offline_row["identity_review_status"] not in {"OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS", "OFFLINE_COMPATIBLE_NAME_VARIANT_EVIDENCE_PASS"}:
            raise ValueError(f"Offline identity evidence mismatch: {record_id}")
        records.append({
            "record_id": record_id,
            "shortlist_id": plan_row["shortlist_id"],
            "cohort": plan_row["cohort"],
            "candidate_identity": {"candidate_host": plan_row["candidate_host"], "candidate_url": plan_row["candidate_url"]},
            "capture": {"snapshot_timestamp": text_row["snapshot_timestamp"], "archive_url": text_row["archive_url"], "text_path": str(text_path), "text_sha256": text_row["text_sha256"], "visible_text_characters": text_row["visible_text_characters"], "text": text_path.read_text(encoding="utf-8")},
            "official_evidence": {
                "iapd": iapd_row,
                "sec_edgar_iapd_offline_review": offline_row,
                "claim_limit": "EDGAR/IAPD identity and host evidence are supporting provenance, not a ground-truth label; the captured artifact must independently align and pass contradiction review.",
            },
            "group_review": {"decision": review_rows[record_id]["group_decision"], "flags": review_rows[record_id]["identity_or_content_flags_for_primary_review"]},
            "review_form": {
                "primary_recommendation": "PENDING_PRIMARY_REVIEW",
                "assessments": {"identity_linkage": "PENDING", "task_relevance": "PENDING", "capture_chronology": "PENDING", "repurpose_or_parking": "PENDING", "contradiction_screen": "PENDING"},
                "supporting_facts": [],
                "uncertainty_reasons": [],
                "rationale": None,
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            },
        })
    return {
        "packet_id": "ISI_SEC_EDGAR_IAPD_PRIMARY_REVIEW_PACKET_V1",
        "status": "FROZEN_UNREVIEWED_PACKET",
        "inputs": {
            "group_packet_sha256": sha256_file(group_packet_path), "group_review_sha256": sha256_file(group_review_path), "group_qa_sha256": sha256_file(group_qa_path),
            "manifest_sha256": sha256_file(manifest_path), "availability_plan_sha256": sha256_file(availability_plan_path), "offline_review_sha256": sha256_file(offline_review_path), "iapd_sha256": sha256_file(iapd_path),
        },
        "review_scope": {
            "allowed_recommendations": ["LEGITIMATE", "UNCERTAIN"],
            "legitimate_requires": ["captured entity/brand linkage", "investment/advisory task relevance", "chronology consistency", "no parking/repurpose indication", "no material contradiction"],
            "source_membership_alone_is_insufficient": True,
            "primary_recommendation_is_not_a_final_label": True,
        },
        "record_count": len(records),
        "records": records,
        "safety_contract": {"network_operations": 0, "model_predictions_visible": False, "labels_created": 0, "training_allowed": False},
    }


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
        raise FileExistsError("Refusing to overwrite primary-review packet")
    packet = build(group_packet_path=args.group_packet, group_review_path=args.group_review, group_qa_path=args.group_qa, manifest_path=args.manifest, availability_plan_path=args.availability_plan, offline_review_path=args.offline_review, iapd_path=args.iapd)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"packet_id": packet["packet_id"], "record_count": packet["record_count"], "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
