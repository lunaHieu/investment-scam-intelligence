"""Combine confirmed-candidate first-pass reports into one human review index."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from validate_external_text_intake import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-pass", type=Path, action="append", required=True)
    parser.add_argument("--brief-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    if len(args.first_pass) != len(args.brief_dir):
        raise ValueError("Each first-pass report must have one matching brief directory")
    for path in (args.output_json, args.output_markdown):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite: {path}")

    records = []
    inputs = []
    seen = set()
    for report_path, brief_dir in zip(args.first_pass, args.brief_dir):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "AI_ASSISTED_FIRST_PASS_HUMAN_CONFIRMATION_REQUIRED":
            raise ValueError(f"Unexpected first-pass status: {report_path}")
        inputs.append({"path": str(report_path), "sha256": sha256_file(report_path)})
        for item in report.get("records", []):
            case_id = str(item["case_id"])
            if case_id in seen:
                raise ValueError(f"Duplicate case ID: {case_id}")
            seen.add(case_id)
            brief_path = brief_dir / f"{case_id}_review_brief_v1.md"
            if not brief_path.is_file():
                raise FileNotFoundError(f"Missing review brief: {brief_path}")
            first_pass = item["ai_first_pass"]
            warning = item["official_warning"]
            snapshot = item["archive_snapshot"]
            records.append(
                {
                    "case_id": case_id,
                    "candidate_id": item["candidate_id"],
                    "candidate_host": item["candidate_host"],
                    "recommended_outcome_for_human_review": first_pass[
                        "recommended_outcome_for_human_review"
                    ],
                    "recommendation_confidence": first_pass["recommendation_confidence"],
                    "local_official_warning_capture_available": warning[
                        "local_capture_available"
                    ],
                    "candidate_identity_visible_in_local_warning": warning[
                        "candidate_identity_visible_in_local_capture"
                    ],
                    "warning_url": warning["url"],
                    "archive_snapshot_url": snapshot["url"],
                    "source_capture_path": snapshot["source_capture_path"],
                    "source_capture_sha256": snapshot["source_capture_sha256"],
                    "text_sha256": snapshot["text_sha256"],
                    "review_brief": str(brief_path),
                    "review_brief_sha256": sha256_file(brief_path),
                    "ground_truth_status": "UNCERTAIN",
                    "review_status": "IN_REVIEW",
                    "external_evaluation_eligible": False,
                }
            )

    records.sort(key=lambda item: item["case_id"])
    output = {
        "analysis_id": "EXTERNAL_TEXT_CONFIRMED_REVIEW_INDEX_V1",
        "created_at": datetime.now().astimezone().isoformat(),
        "status": "TEN_DRAFTS_READY_FOR_HUMAN_RECONCILIATION_ZERO_ELIGIBLE",
        "inputs": inputs,
        "records": records,
        "coverage": {
            "record_count": len(records),
            "confirmed_recommendations_for_human_review": sum(
                item["recommended_outcome_for_human_review"] == "CONFIRMED" for item in records
            ),
            "high_recommendation_count": sum(
                item["recommendation_confidence"] == "HIGH" for item in records
            ),
            "medium_high_recommendation_count": sum(
                item["recommendation_confidence"] == "MEDIUM_HIGH" for item in records
            ),
            "local_official_warning_capture_count": sum(
                item["local_official_warning_capture_available"] for item in records
            ),
            "local_warning_identity_visible_count": sum(
                item["candidate_identity_visible_in_local_warning"] for item in records
            ),
            "human_reconciled_count": 0,
            "external_evaluation_eligible_count": 0,
            "labels_created": 0,
        },
        "manual_follow_up": {
            "official_warning_pages_not_locally_captured": [
                item["case_id"]
                for item in records
                if not item["local_official_warning_capture_available"]
            ],
            "instruction": (
                "Later, inspect the official warning URL for these cases manually if the automated capture "
                "was blocked. Do not copy warning text into the model-input artifact."
            ),
        },
        "decision": {
            "promote_to_confirmed_label": False,
            "change_intake_record_state": False,
            "open_external_scoring": False,
            "next_action": (
                "Human reviewer uses each brief, immutable raw archive capture, and official warning to "
                "confirm identity, contradiction checks, and ground truth."
            ),
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
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Confirmed external-text review index V1",
        "",
        "Có 10 artefact observed-text đã qua kiểm tra tự động và sẵn sàng để con người đối chiếu. "
        "Tất cả vẫn là `UNCERTAIN + LOW + IN_REVIEW`; chưa record nào được dùng để score/train.",
        "",
        "| Case | Host | Gợi ý | Confidence | Local warning | Brief |",
        "|---|---|---|---|---:|---|",
    ]
    for item in records:
        lines.append(
            f"| `{item['case_id']}` | `{item['candidate_host']}` | "
            f"`{item['recommended_outcome_for_human_review']}` | "
            f"`{item['recommendation_confidence']}` | "
            f"{'có' if item['local_official_warning_capture_available'] else 'chưa'} | "
            f"`{item['review_brief']}` |"
        )
    lines.extend(
        [
            "",
            "## Phần bị chặn để làm thủ công sau",
            "",
            *[
                f"- `{case_id}`: mở URL cảnh báo chính thức trong brief để xác nhận; "
                "không đưa nội dung warning vào model input."
                for case_id in output["manual_follow_up"][
                    "official_warning_pages_not_locally_captured"
                ]
            ],
            "",
            "Chỉ sau khi reviewer xác nhận artefact–identity–warning và kiểm tra bằng chứng mâu thuẫn "
            "mới được chuyển record tương ứng thành `CONFIRMED + HIGH + RECONCILED`.",
            "",
        ]
    )
    args.output_markdown.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_json_sha256": sha256_file(args.output_json),
                "output_markdown": str(args.output_markdown),
                "output_markdown_sha256": sha256_file(args.output_markdown),
                "coverage": output["coverage"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
