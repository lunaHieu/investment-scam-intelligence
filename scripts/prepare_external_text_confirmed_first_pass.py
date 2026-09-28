"""Prepare offline AI-assisted first-pass briefs for confirmed candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.confirmed_text_review import assess_confirmed_record
from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file


def write_brief(path: Path, result: dict[str, object]) -> None:
    snapshot = result["archive_snapshot"]
    warning = result["official_warning"]
    first_pass = result["ai_first_pass"]
    lines = [
        f"# Review brief — {result['case_id']}",
        "",
        "## Trạng thái",
        "",
        "Record vẫn là `UNCERTAIN + LOW + IN_REVIEW`; đây chỉ là AI-assisted first pass.",
        "",
        "## Artefact được phép làm model input sau khi duyệt",
        "",
        f"- Candidate host: `{result['candidate_host']}`.",
        f"- Archive snapshot: `{snapshot['url']}`.",
        f"- Snapshot observed at: `{snapshot['snapshot_observed_at']}`.",
        f"- Host trong replay khớp candidate: `{str(snapshot['candidate_host_match']).lower()}`.",
        f"- Full identity-token match: `{str(snapshot['identity_token_check']['any_full_token_match']).lower()}`.",
        f"- Raw SHA-256: `{snapshot['source_capture_sha256']}`.",
        f"- Text SHA-256: `{snapshot['text_sha256']}`.",
        "",
        "Đoạn trích giới hạn:",
        "",
        f"> {snapshot['bounded_excerpt'].replace(chr(10), ' ')}",
        "",
        "## Bằng chứng độc lập — không phải model input",
        "",
        f"- Regulator: `{warning['regulator']['name']}` ({warning['regulator']['jurisdiction']}).",
        f"- Warning URL: `{warning['url']}`.",
        f"- Warning validation date: `{warning['validation_date']}`.",
        f"- Đã có local capture warning: `{str(warning['local_capture_available']).lower()}`.",
        f"- Identity hiện trong local warning capture: `{str(warning['candidate_identity_visible_in_local_capture']).lower()}`.",
        "- Nội dung warning không được đưa vào model input.",
        "",
        "## Khuyến nghị first pass",
        "",
        f"- Identity: `{first_pass['recommended_identity_relationship']}`.",
        f"- Evidence: `{first_pass['recommended_evidence_assessment']}`.",
        f"- Outcome để con người xem xét: `{first_pass['recommended_outcome_for_human_review']}`.",
        f"- Confidence của khuyến nghị: `{first_pass['recommendation_confidence']}`.",
        "",
        first_pass["rationale"],
        "",
        "## Việc reviewer phải xác nhận",
        "",
        *[f"- {item}" for item in result["human_review_required"]],
        "",
        "Chưa được dùng record này để score, train hoặc báo metric.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-registry", type=Path, required=True)
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument("--warning-screen", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--brief-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.brief_dir.exists():
        raise FileExistsError("Refusing to overwrite frozen first-pass output")

    registry = json.loads(args.queue_registry.read_text(encoding="utf-8"))
    queue_outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    queue_info = queue_outputs.get("capture_candidate_queue") or queue_outputs.get(
        "confirmed_reserve_queue", {}
    )
    queue_path = Path(str(queue_info.get("path", "")))
    if sha256_file(queue_path) != queue_info.get("sha256"):
        raise ValueError("Capture candidate queue SHA-256 mismatch")
    queue = {item["candidate_id"]: item for item in load_jsonl(queue_path)}

    intake = json.loads(args.intake.read_text(encoding="utf-8"))
    screen = (
        json.loads(args.warning_screen.read_text(encoding="utf-8"))
        if args.warning_screen is not None
        else {"records": []}
    )
    warning_records = {item["candidate_id"]: item for item in screen.get("records", [])}
    results = []
    for record in intake.get("records", []):
        candidate_id = "EXTCAP_" + str(record["case_id"]).removeprefix("CASE_")
        candidate = queue.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate missing from queue: {candidate_id}")
        results.append(
            assess_confirmed_record(record, candidate, warning_records.get(candidate_id))
        )

    output = {
        "analysis_id": "EXTERNAL_TEXT_CONFIRMED_AI_ASSISTED_FIRST_PASS_V1",
        "status": "AI_ASSISTED_FIRST_PASS_HUMAN_CONFIRMATION_REQUIRED",
        "inputs": {
            "queue_registry": {"path": str(args.queue_registry), "sha256": sha256_file(args.queue_registry)},
            "intake": {"path": str(args.intake), "sha256": sha256_file(args.intake)},
            "warning_screen": (
                {"path": str(args.warning_screen), "sha256": sha256_file(args.warning_screen)}
                if args.warning_screen is not None
                else None
            ),
        },
        "records": results,
        "coverage": {
            "record_count": len(results),
            "same_entity_likely_recommendations": sum(
                item["ai_first_pass"]["recommended_identity_relationship"] == "SAME_ENTITY_LIKELY"
                for item in results
            ),
            "confirmed_recommendations_for_human_review": sum(
                item["ai_first_pass"]["recommended_outcome_for_human_review"] == "CONFIRMED"
                for item in results
            ),
            "local_official_warning_capture_count": sum(
                item["official_warning"]["local_capture_available"] for item in results
            ),
            "human_confirmed_records": 0,
            "external_evaluation_eligible_records": 0,
            "labels_created": 0,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "warning_text_used_as_model_input": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "raw_files_modified": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.brief_dir.mkdir(parents=True, exist_ok=False)
    for result in results:
        write_brief(args.brief_dir / f"{result['case_id']}_review_brief_v1.md", result)
    print(json.dumps(output, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
