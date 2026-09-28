"""Materialize the adopted 21-case external-text reconciled intake."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.external_text_reconciled_intake import materialize_reconciled_record
from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def ai_report_from_registry(path: Path) -> tuple[dict, Path, str]:
    registry = load_json(path)
    if registry.get("analysis_id") != "EXTERNAL_TEXT_AI_MANUAL_ADJUDICATION_V1":
        raise ValueError("Unexpected AI adjudication registry")
    outputs = [item for item in registry.get("outputs", []) if item.get("role") == "ai_adjudication_json"]
    if len(outputs) != 1:
        raise ValueError("AI adjudication registry has no unique JSON output")
    output = Path(str(outputs[0].get("path", "")))
    actual = sha256_file(output) if output.is_file() else None
    if actual != outputs[0].get("sha256"):
        raise ValueError("AI adjudication artifact is missing or changed")
    return load_json(output), output, str(actual)


def write_markdown(path: Path, batch: dict[str, object]) -> None:
    counts = Counter(item["ground_truth_status"] for item in batch["records"])
    lines = [
        "# External-text reconciled intake V1",
        "",
        "Batch này được materialize từ AI manual adjudication đã được project owner cho phép tiếp tục. "
        "Nó không tuyên bố project owner đã tự đọc lại độc lập từng evidence.",
        "",
        f"- Tổng: {len(batch['records'])}",
        f"- CONFIRMED: {counts['CONFIRMED']}",
        f"- LEGITIMATE: {counts['LEGITIMATE']}",
        "- Tất cả record: `HIGH + RECONCILED`",
        "- Raw capture và text không bị sửa.",
        "",
        "| Case | Label | Host/source URL | Confidence | Review |",
        "|---|---|---|---|---|",
    ]
    for record in sorted(batch["records"], key=lambda item: item["case_id"]):
        lines.append(
            f"| `{record['case_id']}` | `{record['ground_truth_status']}` | "
            f"{record['artifact']['url']} | `HIGH` | `RECONCILED` |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adoption", type=Path, required=True)
    parser.add_argument("--ai-registry", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.output_json, args.output_markdown):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")

    adoption = load_json(args.adoption)
    if adoption.get("adoption_id") != "EXTERNAL_TEXT_RECONCILIATION_ADOPTION_V1":
        raise ValueError("Unexpected adoption ID")
    ai_report, ai_path, ai_hash = ai_report_from_registry(args.ai_registry)
    if ai_report.get("status") != "TWENTY_ONE_AI_REVIEWS_COMPLETE_HUMAN_CONFIRMATION_PENDING_ZERO_ELIGIBLE":
        raise ValueError("Unexpected AI adjudication status")
    source_records: dict[str, dict] = {}
    source_inputs = []
    for item in adoption.get("source_intakes", []):
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            raise ValueError(f"Source intake missing or changed: {path}")
        batch = load_json(path)
        for record in batch.get("records", []):
            case_id = record.get("case_id")
            if case_id in source_records:
                raise ValueError(f"Duplicate source case: {case_id}")
            source_records[case_id] = record
        source_inputs.append({"role": item.get("role"), "path": str(path), "sha256": actual})
    ai_records = {item["case_id"]: item for item in ai_report.get("records", [])}
    if len(source_records) != 21 or set(source_records) != set(ai_records):
        raise ValueError("Expected identical 21-case coverage in source and AI records")

    records = [
        materialize_reconciled_record(source_records[case_id], ai_records[case_id], adoption)
        for case_id in sorted(source_records)
    ]
    counts = Counter(item["ground_truth_status"] for item in records)
    if counts != Counter({"LEGITIMATE": 11, "CONFIRMED": 10}):
        raise ValueError(f"Unexpected label counts: {dict(counts)}")
    batch = {
        "batch_id": "EXTERNAL_TEXT_RECONCILED_PILOT_V1",
        "status": "RECONCILED",
        "policy_id": "ISI_TEXT_BASELINE_V2_EXTERNAL_EVAL_POLICY_V1",
        "created_at": adoption["adopted_at"],
        "source_scope": [
            "sec_iapd_homepage_capture_2026_09_24",
            "wayback_confirmed_capture_2026_09_24",
        ],
        "materialization_inputs": {
            "adoption": {"path": str(args.adoption), "sha256": sha256_file(args.adoption)},
            "ai_adjudication": {"path": str(ai_path), "sha256": ai_hash},
            "source_intakes": source_inputs,
        },
        "review_policy": {
            "ai_manual_review_completed": True,
            "human_owner_adopted_recommendations": True,
            "independent_human_evidence_rereview_claimed": False,
            "warning_text_used_as_model_input": False,
        },
        "records": records,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(args.output_markdown, batch)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_json_sha256": sha256_file(args.output_json),
                "output_markdown": str(args.output_markdown),
                "output_markdown_sha256": sha256_file(args.output_markdown),
                "record_count": len(records),
                "label_counts": dict(counts),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

