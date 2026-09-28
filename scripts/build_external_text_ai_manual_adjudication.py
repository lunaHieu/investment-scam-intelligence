"""Build the frozen AI manual-adjudication layer for 21 external-text cases."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.external_text_ai_adjudication import build_ai_adjudication_record
from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def frozen_output(registry_path: Path, analysis_id: str, role: str) -> tuple[dict, Path, str]:
    registry = load_json(registry_path)
    if registry.get("analysis_id") != analysis_id:
        raise ValueError(f"Unexpected analysis ID in {registry_path}")
    matches = [item for item in registry.get("outputs", []) if item.get("role") == role]
    if len(matches) != 1:
        raise ValueError(f"Expected one {role} output in {registry_path}")
    path = Path(str(matches[0].get("path", "")))
    actual = sha256_file(path) if path.is_file() else None
    if actual != matches[0].get("sha256"):
        raise ValueError(f"Frozen output missing or changed: {path}")
    return load_json(path), path, str(actual)


def write_markdown(path: Path, report: dict[str, object]) -> None:
    lines = [
        "# External-text AI manual adjudication V1",
        "",
        "Đây là vòng review thủ công do AI thực hiện theo ủy quyền của người dùng. Kết quả là "
        "khuyến nghị có kiểm soát, không phải xác nhận của con người và chưa tạo ground truth.",
        "",
        "## Kết quả",
        "",
        "- 21/21 case đã được AI đọc và đối chiếu.",
        "- 10 case được đề xuất `CONFIRMED`; 11 case được đề xuất `LEGITIMATE`.",
        "- 21/21 khuyến nghị ở mức `HIGH` trong phạm vi bằng chứng đã đóng băng.",
        "- 0 human confirmation, 0 label, 0 case được mở external evaluation.",
        "",
        "| Case | Branch | Host | AI recommendation | Confidence | Official evidence | Human gate |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in report["records"]:
        ai = record["ai_review"]
        official = ai["official_evidence"]
        lines.append(
            f"| `{record['case_id']}` | `{record['branch']}` | `{record['candidate_host']}` | "
            f"`{ai['recommended_decision']}` | `{ai['recommended_confidence']}` | "
            f"`{official['review_status']}` | `PENDING` |"
        )
    lines.extend(
        [
            "",
            "## Ranh giới sử dụng",
            "",
            "- Không truy cập trực tiếp các domain ứng viên đáng ngờ; chỉ đọc snapshot lưu trữ và nguồn quản lý chính thức.",
            "- Nội dung cảnh báo của cơ quan quản lý không được đưa vào model input.",
            "- SEC/IAPD registration được dùng để đối chiếu danh tính/host, không được diễn giải thành bảo đảm an toàn.",
            "- Muốn materialize nhãn vẫn cần một hành động chấp nhận riêng ở cổng human review.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook-registry", type=Path, required=True)
    parser.add_argument("--confirmed-registry", type=Path, required=True)
    parser.add_argument("--legitimate-registry", type=Path, required=True)
    parser.add_argument("--specification", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.output_json, args.output_markdown):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")

    workbook, workbook_path, workbook_hash = frozen_output(
        args.workbook_registry,
        "EXTERNAL_TEXT_REVIEWER_DECISION_WORKBOOK_V1",
        "reviewer_workbook_json",
    )
    confirmed, confirmed_path, confirmed_hash = frozen_output(
        args.confirmed_registry,
        "EXTERNAL_TEXT_CONFIRMED_RECONCILIATION_PACKET_V1",
        "decision_packet_json",
    )
    legitimate, legitimate_path, legitimate_hash = frozen_output(
        args.legitimate_registry,
        "EXTERNAL_TEXT_LEGITIMATE_RECONCILIATION_PACKET_V1",
        "decision_packet_json",
    )
    specification = load_json(args.specification)
    if specification.get("specification_id") != "EXTERNAL_TEXT_AI_MANUAL_ADJUDICATION_SPEC_V1":
        raise ValueError("Unexpected specification ID")
    specs = {
        item["case_id"]: {
            **item,
            "reviewed_at": specification.get("reviewed_at"),
            "authorization": specification.get("authorization"),
        }
        for item in specification.get("records", [])
    }
    if len(specs) != 21:
        raise ValueError("Expected 21 unique adjudication specifications")
    packets = {item["case_id"]: item for item in confirmed.get("records", [])}
    packets.update({item["case_id"]: item for item in legitimate.get("records", [])})
    forms = {item["case_id"]: item for item in workbook.get("records", [])}
    if set(specs) != set(packets) or set(specs) != set(forms):
        raise ValueError("Case coverage differs across specification, packets, and workbook")

    records = [
        build_ai_adjudication_record(forms[case_id], packets[case_id], specs[case_id])
        for case_id in sorted(specs)
    ]
    decisions = Counter(item["ai_review"]["recommended_decision"] for item in records)
    confidences = Counter(item["ai_review"]["recommended_confidence"] for item in records)
    report = {
        "analysis_id": "EXTERNAL_TEXT_AI_MANUAL_ADJUDICATION_V1",
        "created_at": specification["reviewed_at"],
        "status": "TWENTY_ONE_AI_REVIEWS_COMPLETE_HUMAN_CONFIRMATION_PENDING_ZERO_ELIGIBLE",
        "purpose": (
            "Record an auditable AI manual assessment of all 21 frozen external-text cases "
            "without impersonating a human reviewer, mutating intake, or creating labels."
        ),
        "inputs": {
            "reviewer_workbook": {"path": str(workbook_path), "sha256": workbook_hash},
            "confirmed_packet": {"path": str(confirmed_path), "sha256": confirmed_hash},
            "legitimate_packet": {"path": str(legitimate_path), "sha256": legitimate_hash},
            "adjudication_specification": {
                "path": str(args.specification),
                "sha256": sha256_file(args.specification),
            },
        },
        "review_policy": {
            "reviewer_type": "AI_AGENT",
            "human_confirmation_recorded": False,
            "recommendation_is_ground_truth": False,
            "candidate_live_domain_access_allowed": False,
            "warning_text_used_as_model_input": False,
            "separate_human_adoption_required_for_materialization": True,
        },
        "records": records,
        "coverage": {
            "record_count": len(records),
            "ai_review_completed_count": sum(
                item["ai_review"]["status"] == "COMPLETED" for item in records
            ),
            "confirmed_recommendation_count": decisions["CONFIRMED"],
            "legitimate_recommendation_count": decisions["LEGITIMATE"],
            "high_confidence_recommendation_count": confidences["HIGH"],
            "ready_for_human_adoption_count": sum(
                item["ai_review"]["ready_for_human_adoption"] for item in records
            ),
            "human_confirmation_count": 0,
            "ready_for_reconciled_intake_count": 0,
            "labels_created": 0,
            "external_evaluation_eligible_count": 0,
        },
        "decision_gate": {
            "ai_manual_review_complete": True,
            "materialize_reconciled_intake": False,
            "open_external_scoring": False,
            "reason": "AI recommendations are complete; human adoption has not been recorded.",
        },
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "official_reference_checks_for_confirmed_cases": 10,
            "source_intake_files_modified": False,
            "warning_text_used_as_model_input": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(args.output_markdown, report)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_json_sha256": sha256_file(args.output_json),
                "output_markdown": str(args.output_markdown),
                "output_markdown_sha256": sha256_file(args.output_markdown),
                "coverage": report["coverage"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
