"""Inspect captured official warnings offline for linked preserved artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.official_warning_artifacts import analyze_warning_capture
from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-registry", type=Path, required=True)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    queue_registry = json.loads(args.queue_registry.read_text(encoding="utf-8"))
    outputs = {item.get("role"): item for item in queue_registry.get("outputs", [])}
    queue_info = outputs.get("capture_candidate_queue") or outputs.get("confirmed_reserve_queue") or {}
    queue_path = Path(str(queue_info.get("path", "")))
    if sha256_file(queue_path) != queue_info.get("sha256"):
        raise ValueError("Capture candidate queue SHA-256 mismatch")
    queue = {item["candidate_id"]: item for item in load_jsonl(queue_path)}

    capture_report = json.loads(args.capture_report.read_text(encoding="utf-8"))
    captured = [item for item in capture_report.get("results", []) if item.get("outcome") == "CAPTURED"]
    records = []
    for item in captured:
        candidate = queue.get(item.get("candidate_id"))
        if candidate is None or candidate.get("target_outcome") not in {
            "CONFIRMED_CANDIDATE",
            "CONFIRMED_RESERVE_CANDIDATE",
        }:
            raise ValueError(f"Unexpected captured candidate: {item.get('candidate_id')}")
        path = Path(str(item.get("path", "")))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Captured warning file missing or changed: {path}")
        records.append(analyze_warning_capture(candidate=candidate, capture_path=path))

    result = {
        "analysis_id": "OFFICIAL_WARNING_PRESERVED_ARTIFACT_SCREEN_V2",
        "status": "OFFLINE_SCREEN_COMPLETE_NO_MODEL_INPUT_CREATED",
        "inputs": {
            "queue_registry": str(args.queue_registry),
            "queue_sha256": queue_info.get("sha256"),
            "capture_report": str(args.capture_report),
            "capture_report_sha256": sha256_file(args.capture_report),
        },
        "records": records,
        "coverage": {
            "captured_official_warning_count": len(records),
            "warnings_with_candidate_host_in_text": sum(item["candidate_host_in_visible_text"] for item in records),
            "warnings_with_document_attachment": sum(item["document_attachment_count"] > 0 for item in records),
            "warnings_with_identity_relevant_document": sum(
                item["identity_relevant_document_count"] > 0 for item in records
            ),
            "warnings_with_identity_relevant_media": sum(item["identity_relevant_media_count"] > 0 for item in records),
            "follow_up_asset_count": sum(item["follow_up_asset_count"] for item in records),
            "observed_solicitation_artifact_count": 0,
            "labels_created": 0,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "warning_page_as_model_input_allowed": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
