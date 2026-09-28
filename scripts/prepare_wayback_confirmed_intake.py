"""Prepare unlabeled review drafts from locally captured Wayback snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file
from src.isi.normalization.wayback_external_text import (
    archived_capture_to_draft_record,
    screen_archived_capture,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-registry", type=Path, required=True)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--batch-id", default="EXTERNAL_TEXT_CONFIRMED_WAYBACK_PILOT_V1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    datetime.strptime(args.capture_date, "%Y-%m-%d")

    registry = json.loads(args.queue_registry.read_text(encoding="utf-8"))
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    queue_info = outputs.get("capture_candidate_queue") or outputs.get("confirmed_reserve_queue") or {}
    queue_path = Path(str(queue_info.get("path", "")))
    if sha256_file(queue_path) != queue_info.get("sha256"):
        raise ValueError("Capture candidate queue SHA-256 mismatch")
    queue = {item["candidate_id"]: item for item in load_jsonl(queue_path)}

    capture_report = json.loads(args.capture_report.read_text(encoding="utf-8"))
    profiles = []
    records = []
    for item in capture_report.get("results", []):
        if item.get("outcome") != "CAPTURED":
            continue
        candidate = queue.get(item.get("candidate_id"))
        if candidate is None or candidate.get("target_outcome") not in {
            "CONFIRMED_CANDIDATE",
            "CONFIRMED_RESERVE_CANDIDATE",
        }:
            raise ValueError(f"Unexpected candidate in capture report: {item.get('candidate_id')}")
        capture_path = Path(str(item.get("path", "")))
        if not capture_path.is_file() or sha256_file(capture_path) != item.get("sha256"):
            raise ValueError(f"Capture missing or changed: {capture_path}")
        resolved_root = args.raw_root.resolve()
        resolved_capture = capture_path.resolve()
        if not resolved_capture.is_relative_to(resolved_root):
            raise ValueError(f"Capture is outside raw root: {capture_path}")
        relative = resolved_capture.relative_to(resolved_root).as_posix()
        profile, text, _ = screen_archived_capture(candidate=candidate, capture_path=capture_path)
        profiles.append(profile)
        if profile["screening_decision"] == "REVIEWABLE_OBSERVED_TEXT":
            records.append(
                archived_capture_to_draft_record(
                    candidate=candidate,
                    capture_item=item,
                    capture_path=capture_path,
                    capture_relative_path=relative,
                    collection_date=args.capture_date,
                    profile=profile,
                    text=text,
                )
            )

    batch = {
        "batch_id": args.batch_id,
        "status": "IN_REVIEW",
        "policy_id": "ISI_TEXT_BASELINE_V2_EXTERNAL_EVAL_POLICY_V1",
        "created_at": datetime.now().astimezone().isoformat(),
        "source_scope": ["wayback_confirmed_capture_2026_09_24"],
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    decisions = {}
    for profile in profiles:
        key = str(profile["screening_decision"])
        decisions[key] = decisions.get(key, 0) + 1
    report = {
        "analysis_id": "EXTERNAL_TEXT_CONFIRMED_WAYBACK_PREPARATION_V1",
        "status": "DRAFTS_CREATED_HUMAN_RECONCILIATION_REQUIRED",
        "inputs": {
            "queue_registry": str(args.queue_registry),
            "queue_sha256": queue_info.get("sha256"),
            "capture_report": str(args.capture_report),
            "capture_report_sha256": sha256_file(args.capture_report),
        },
        "capture_profiles": profiles,
        "screening_counts": decisions,
        "output": {
            "path": str(args.output),
            "sha256": sha256_file(args.output),
            "record_count": len(records),
        },
        "readiness": {
            "reviewable_draft_records": len(records),
            "human_reconciled_records": 0,
            "external_evaluation_eligible_records": 0,
        },
        "safety_contract": {
            "network_operations_during_offline_preparation": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "raw_files_modified": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
