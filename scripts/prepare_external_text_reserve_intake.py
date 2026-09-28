"""Prepare an offline intake draft from captured SEC reserve homepages."""

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
from src.isi.normalization.external_text import capture_to_draft_record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-registry", required=True, type=Path)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--candidate-id", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    datetime.strptime(args.capture_date, "%Y-%m-%d")

    registry = json.loads(args.queue_registry.read_text(encoding="utf-8"))
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    queue_info = outputs.get("sec_legitimate_reserve_queue", {})
    queue_path = Path(str(queue_info.get("path", "")))
    if sha256_file(queue_path) != queue_info.get("sha256"):
        raise ValueError("SEC legitimate reserve queue SHA-256 mismatch")
    queue = {item["candidate_id"]: item for item in load_jsonl(queue_path)}

    records = []
    profiles = []
    for candidate_id in args.candidate_id:
        candidate = queue.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Unknown candidate ID: {candidate_id}")
        if (
            candidate.get("target_outcome") != "LEGITIMATE_RESERVE_CANDIDATE"
            or candidate.get("source_id") != "sec_iapd"
        ):
            raise ValueError(f"Only SEC/IAPD legitimate reserve candidates are allowed: {candidate_id}")
        host = str(candidate["candidate_host"])
        relative = (
            Path("external_text_captures")
            / args.capture_date
            / "legitimate"
            / f"{candidate_id}__{host}.html"
        )
        capture_path = args.raw_root / relative
        if not capture_path.is_file():
            raise FileNotFoundError(f"Missing capture: {capture_path}")
        observed = datetime.fromtimestamp(capture_path.stat().st_mtime).astimezone().isoformat()
        record, profile = capture_to_draft_record(
            candidate=candidate,
            capture_path=capture_path,
            capture_relative_path=relative.as_posix(),
            content_observed_at=observed,
            collection_date=args.capture_date,
        )
        records.append(record)
        profiles.append(profile)

    batch = {
        "batch_id": "EXTERNAL_TEXT_LEGITIMATE_RESERVE_CAPTURE_V1",
        "status": "IN_REVIEW",
        "policy_id": "ISI_TEXT_BASELINE_V2_EXTERNAL_EVAL_POLICY_V1",
        "created_at": datetime.now().astimezone().isoformat(),
        "source_scope": ["sec_iapd_homepage_capture_2026_09_24"],
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "analysis_id": "EXTERNAL_TEXT_LEGITIMATE_RESERVE_CAPTURE_V1",
        "status": "DRAFT_CAPTURED_IDENTITY_REVIEW_REQUIRED",
        "input_queue": {
            "registry": str(args.queue_registry),
            "path": str(queue_path),
            "sha256": queue_info.get("sha256"),
        },
        "capture_profiles": profiles,
        "output": {
            "path": str(args.output),
            "sha256": sha256_file(args.output),
            "record_count": len(records),
        },
        "readiness": {
            "captured_records": len(records),
            "human_reconciled_records": 0,
            "external_evaluation_eligible_records": 0,
        },
        "safety_contract": {
            "network_operations_during_offline_preparation": 0,
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
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
