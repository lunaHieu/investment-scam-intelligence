"""Build a frozen, non-mutating second-pass packet for confirmed drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.confirmed_reconciliation_review import assess_reconciliation_record
from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _verify_declared_file(item: dict[str, object], role: str) -> Path:
    path = Path(str(item.get("path", "")))
    if not path.is_file():
        raise FileNotFoundError(f"Missing {role}: {path}")
    actual = sha256_file(path)
    if actual != item.get("sha256"):
        raise ValueError(f"SHA-256 mismatch for {role}: {path}")
    return path


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _warning_capture_state(record: dict[str, object]) -> str:
    warning = record["regulator_evidence"]
    if warning["candidate_identity_visible_in_local_capture"]:
        return "IDENTITY_VISIBLE"
    if warning["local_capture_available"]:
        return "CAPTURE_PRESENT_IDENTITY_NOT_VISIBLE"
    return "NOT_LOCALLY_CAPTURED"


def write_markdown(path: Path, packet: dict[str, object]) -> None:
    lines = [
        "# Confirmed external-text reconciliation packet V1",
        "",
        "Đây là đối soát tự động vòng hai trên artefact local đã đóng băng. Kết quả chỉ là "
        "decision aid; cả 10 record vẫn là `UNCERTAIN + LOW + IN_REVIEW`, chưa record nào "
        "được dùng để score hoặc train.",
        "",
        "## Tóm tắt",
        "",
        "| Case | Host | Warning class | Local warning | Snapshot trước reference | Hard contradiction | Đề xuất |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for record in packet["records"]:
        linkage = record["identity_and_time_linkage"]
        warning = record["regulator_evidence"]
        contradiction = record["contradiction_review"]
        proposal = record["automated_second_pass"]
        lines.append(
            f"| `{record['case_id']}` | `{record['candidate_host']}` | "
            f"`{warning['warning_classification']['evidence_class']}` | "
            f"`{_warning_capture_state(record)}` | "
            f"{linkage['days_snapshot_precedes_reference']} ngày | "
            f"{contradiction['hard_contradiction_count']} | "
            f"`{proposal['proposed_outcome_for_human_review']}` |"
        )

    lines.extend(
        [
            "",
            "## Cách đọc",
            "",
            "- `Hard contradiction` là lỗi làm hỏng chuỗi liên kết tự động, ví dụ sai hash, "
            "không khớp host/danh tính hoặc snapshot sau ngày reference.",
            "- `Caution` là điểm reviewer phải chú ý; nó không tự động bác bỏ case. Claim "
            "‘licensed/regulated/safe’ trên chính trang candidate chỉ là self-claim.",
            "- Nội dung warning của regulator là evidence độc lập và tuyệt đối không được ghép vào model input.",
            "",
        ]
    )
    for record in packet["records"]:
        linkage = record["identity_and_time_linkage"]
        warning = record["regulator_evidence"]
        contradiction = record["contradiction_review"]
        proposal = record["automated_second_pass"]
        lines.extend(
            [
                f"## {record['case_id']} — {record['candidate_host']}",
                "",
                f"- Snapshot: `{linkage['snapshot_observed_date']}`; reference validation: "
                f"`{linkage['reference_validation_date']}`; chênh lệch: "
                f"`{linkage['days_snapshot_precedes_reference']}` ngày.",
                f"- Host match: `{str(linkage['archive_replay_targets_candidate_host']).lower()}`; "
                f"identity full-token match: "
                f"`{str(linkage['identity_token_check']['any_full_token_match']).lower()}`.",
                f"- Regulator: `{warning['regulator']['name']}` "
                f"({warning['regulator']['jurisdiction']}); class: "
                f"`{warning['warning_classification']['evidence_class']}`.",
                f"- Local warning state: `{_warning_capture_state(record)}`.",
                f"- Hard contradictions: "
                f"`{', '.join(contradiction['hard_contradictions']) or 'NONE'}`.",
                f"- Cautions: `{', '.join(contradiction['caution_flags']) or 'NONE'}`.",
                f"- Automated proposal: `{proposal['proposed_outcome_for_human_review']}` / "
                f"`{proposal['recommendation_confidence']}`; không phải ground truth.",
                "",
                "Tín hiệu trong preserved candidate text:",
                "",
            ]
        )
        for name, signal in record["preserved_text_signal_profile"].items():
            state = "có" if signal["detected"] else "không"
            lines.append(f"- `{name}`: {state} ({signal['match_count']} matches).")
            for context in signal["bounded_contexts"][:1]:
                lines.append(f"  - `{context['matched_text']}` — “{context['context']}”")
        lines.extend(
            [
                "",
                "Human decision: `CHƯA ĐIỀN` — reviewer, rationale, contradictory evidence và "
                "final confidence đều để trống trong JSON.",
                "",
            ]
        )

    lines.extend(
        [
            "## Gate cuối",
            "",
            "Chỉ được tạo bản intake reconciled sau khi con người xác nhận từng case. Bản packet này "
            "không thay đổi file intake, không tạo label và không mở external scoring.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-registry", type=Path, required=True)
    parser.add_argument("--review-index", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.output_json, args.output_markdown):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")

    pilot = load_json(args.pilot_registry)
    review_index = load_json(args.review_index)
    if pilot.get("pilot_id") != "EXTERNAL_TEXT_CONFIRMED_CAPTURE_PILOT_V1":
        raise ValueError("Unexpected confirmed-pilot registry")
    if review_index.get("analysis_id") != "EXTERNAL_TEXT_CONFIRMED_REVIEW_INDEX_V1":
        raise ValueError("Unexpected review index")

    outputs = {str(item.get("role")): item for item in pilot.get("outputs", [])}
    intake_items = [outputs[name] for name in sorted(outputs) if name.startswith("intake_")]
    first_pass_items = [
        outputs[name] for name in sorted(outputs) if name.startswith("first_pass_")
    ]
    if len(intake_items) != 4 or len(first_pass_items) != 4:
        raise ValueError("Expected four intake batches and four first-pass batches")

    intake_records: dict[str, dict[str, object]] = {}
    intake_inputs: list[dict[str, object]] = []
    for item in intake_items:
        path = _verify_declared_file(item, str(item.get("role")))
        batch = load_json(path)
        intake_inputs.append({"path": str(path), "sha256": sha256_file(path)})
        for record in batch.get("records", []):
            case_id = str(record.get("case_id"))
            if case_id in intake_records:
                raise ValueError(f"Duplicate intake case: {case_id}")
            intake_records[case_id] = record

    first_pass_records: dict[str, dict[str, object]] = {}
    first_pass_inputs: list[dict[str, object]] = []
    for item in first_pass_items:
        path = _verify_declared_file(item, str(item.get("role")))
        report = load_json(path)
        first_pass_inputs.append({"path": str(path), "sha256": sha256_file(path)})
        for record in report.get("records", []):
            case_id = str(record.get("case_id"))
            if case_id in first_pass_records:
                raise ValueError(f"Duplicate first-pass case: {case_id}")
            first_pass_records[case_id] = record

    indexed_case_ids = {str(item.get("case_id")) for item in review_index.get("records", [])}
    if set(intake_records) != set(first_pass_records) or set(intake_records) != indexed_case_ids:
        raise ValueError("Case IDs differ across intake, first pass, and review index")
    if len(intake_records) != 10:
        raise ValueError("Expected exactly ten confirmed drafts")

    raw_root = Path(str(pilot.get("raw_root", "")))
    results = []
    integrity_errors = []
    for case_id in sorted(intake_records):
        record = intake_records[case_id]
        artifact = record.get("artifact", {})
        raw_path = raw_root / str(artifact.get("source_capture_path", ""))
        raw_valid = bool(
            raw_path.is_file()
            and sha256_file(raw_path) == artifact.get("source_capture_sha256")
        )
        text = str(artifact.get("text", ""))
        text_valid = _text_sha256(text) == artifact.get("text_sha256")
        if not raw_valid or not text_valid:
            integrity_errors.append(case_id)
        results.append(
            assess_reconciliation_record(
                record,
                first_pass_records[case_id],
                raw_capture_hash_valid=raw_valid,
                text_hash_valid=text_valid,
            )
        )
    if integrity_errors:
        raise ValueError(f"Source integrity failed; no packet written: {integrity_errors}")

    hard_cases = [
        item["case_id"]
        for item in results
        if item["contradiction_review"]["hard_contradiction_count"]
    ]
    manual_warning_follow_up = [
        item["case_id"]
        for item in results
        if not item["regulator_evidence"]["candidate_identity_visible_in_local_capture"]
    ]
    packet = {
        "analysis_id": "EXTERNAL_TEXT_CONFIRMED_RECONCILIATION_PACKET_V1",
        "created_at": datetime.now().astimezone().isoformat(),
        "status": "SECOND_PASS_COMPLETE_HUMAN_DECISION_REQUIRED_ZERO_ELIGIBLE",
        "purpose": (
            "Provide a reproducible second-pass contradiction and claim review for ten frozen "
            "confirmed-candidate drafts without creating ground truth or changing intake state."
        ),
        "inputs": {
            "pilot_registry": {
                "path": str(args.pilot_registry),
                "sha256": sha256_file(args.pilot_registry),
            },
            "review_index": {
                "path": str(args.review_index),
                "sha256": sha256_file(args.review_index),
            },
            "intakes": intake_inputs,
            "first_pass_reports": first_pass_inputs,
        },
        "method": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "source": "Only frozen local intake text, raw hashes, and frozen first-pass metadata.",
            "automatic_gates": list(
                results[0]["contradiction_review"]["automatic_gate_results"].keys()
            ),
            "caution_policy": (
                "Caution flags require reviewer attention but are not treated as automatic "
                "contradictions or proof of ground truth."
            ),
        },
        "records": results,
        "coverage": {
            "record_count": len(results),
            "raw_capture_hash_valid_count": sum(
                item["source_integrity"]["raw_capture_hash_valid"] for item in results
            ),
            "normalized_text_hash_valid_count": sum(
                item["source_integrity"]["normalized_text_hash_valid"] for item in results
            ),
            "all_automatic_gates_pass_count": sum(
                item["automated_second_pass"]["all_automatic_gates_pass"] for item in results
            ),
            "hard_contradiction_case_count": len(hard_cases),
            "confirmed_proposal_for_human_review_count": sum(
                item["automated_second_pass"]["proposed_outcome_for_human_review"]
                == "CONFIRMED"
                for item in results
            ),
            "local_warning_identity_visible_count": sum(
                item["regulator_evidence"]["candidate_identity_visible_in_local_capture"]
                for item in results
            ),
            "manual_warning_follow_up_count": len(manual_warning_follow_up),
            "human_decision_count": 0,
            "external_evaluation_eligible_count": 0,
            "labels_created": 0,
        },
        "manual_follow_up": {
            "case_ids": manual_warning_follow_up,
            "instruction": (
                "Later, inspect the official warning in a browser for these cases and record the "
                "human decision. Do not copy warning text into model input."
            ),
        },
        "decision_gate": {
            "hard_contradiction_case_ids": hard_cases,
            "human_confirmation_required": True,
            "promote_to_confirmed_label": False,
            "change_intake_record_state": False,
            "open_external_scoring": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "warning_text_used_as_model_input": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "raw_files_modified": False,
            "intake_files_modified": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(args.output_markdown, packet)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_json_sha256": sha256_file(args.output_json),
                "output_markdown": str(args.output_markdown),
                "output_markdown_sha256": sha256_file(args.output_markdown),
                "coverage": packet["coverage"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
