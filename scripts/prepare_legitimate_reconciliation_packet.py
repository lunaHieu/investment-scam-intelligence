"""Build a frozen, non-mutating second-pass packet for legitimate drafts."""

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

from src.isi.curation.legitimate_reconciliation_review import (
    assess_legitimate_reconciliation_record,
)
from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _declared_output(registry: dict[str, object], role: str) -> Path:
    matches = [item for item in registry.get("outputs", []) if item.get("role") == role]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one output role {role}")
    item = matches[0]
    path = Path(str(item.get("path", "")))
    if not path.is_file() or sha256_file(path) != item.get("sha256"):
        raise ValueError(f"Missing or changed declared output: {role}")
    return path


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_markdown(path: Path, packet: dict[str, object]) -> None:
    lines = [
        "# Legitimate external-text reconciliation packet V1",
        "",
        "Đây là đối soát tự động vòng hai trên 11 artefact local đã đóng băng. "
        "Kết quả chỉ là decision aid; mọi record vẫn `UNCERTAIN + LOW + IN_REVIEW`, "
        "chưa có label hay record external-evaluation-eligible.",
        "",
        "## Tóm tắt",
        "",
        "| Case | Host | CRD | Contacts | Text chars | Hard contradiction | Đề xuất |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for record in packet["records"]:
        sec = record["sec_identity_and_registration"]
        contacts = sec["contact_field_check"]
        contradiction = record["contradiction_review"]
        proposal = record["automated_second_pass"]
        lines.append(
            f"| `{record['case_id']}` | `{record['candidate_host']}` | `{sec['crd']}` | "
            f"{contacts['matched_count']}/{contacts['available_count']} | "
            f"{record['source_integrity']['visible_text_characters']} | "
            f"{contradiction['hard_contradiction_count']} | "
            f"`{proposal['proposed_outcome_for_human_review']}` |"
        )
    lines.extend(
        [
            "",
            "## Cách đọc",
            "",
            "- SEC/IAPD registration và filed host hỗ trợ đối chiếu identity; không phải chứng nhận "
            "rằng mọi nội dung trên website đều an toàn hoặc chính xác.",
            "- `Hard contradiction` là gate khách quan bị hỏng: hash, CRD, host, identity, "
            "registration state, chronology hoặc source state.",
            "- `Caution` là điểm cần reviewer xem kỹ, không tự động bác bỏ case.",
            "",
        ]
    )
    for record in packet["records"]:
        sec = record["sec_identity_and_registration"]
        contradiction = record["contradiction_review"]
        proposal = record["automated_second_pass"]
        lines.extend(
            [
                f"## {record['case_id']} — {record['candidate_host']}",
                "",
                f"- CRD/SEC: `{sec['crd']}` / `{sec['sec_number']}`; business name: "
                f"`{sec['business_name']}`.",
                f"- Registration: `{sec['registration'].get('FirmType')}` / "
                f"`{sec['registration'].get('St')}`; filing: `{sec['filing_date']}`; "
                f"capture: `{sec['capture_observed_date']}`.",
                f"- Filed host exact match: `{str(sec['captured_host_exactly_listed']).lower()}`; "
                f"identity full-token match: "
                f"`{str(sec['identity_token_check']['any_full_token_match']).lower()}`.",
                f"- Contact matches: `{sec['contact_field_check']['matched_count']}/"
                f"{sec['contact_field_check']['available_count']}`.",
                f"- Hard contradictions: "
                f"`{', '.join(contradiction['hard_contradictions']) or 'NONE'}`.",
                f"- Cautions: `{', '.join(contradiction['caution_flags']) or 'NONE'}`.",
                f"- Automated proposal: `{proposal['proposed_outcome_for_human_review']}` / "
                f"`{proposal['recommendation_confidence']}`; không phải ground truth.",
                "",
                "Context signals trong preserved website text:",
                "",
            ]
        )
        for name, signal in record["preserved_text_context_profile"].items():
            state = "có" if signal["detected"] else "không"
            lines.append(f"- `{name}`: {state} ({signal['match_count']} matches).")
            for context in signal["bounded_contexts"][:1]:
                lines.append(f"  - `{context['matched_text']}` — “{context['context']}”")
        lines.extend(
            [
                "",
                "Human decision: `CHƯA ĐIỀN`; site-control và contradictory-evidence check "
                "vẫn để trống trong JSON.",
                "",
            ]
        )
    lines.extend(
        [
            "## Gate cuối",
            "",
            "Chỉ tạo intake reconciled mới sau khi con người xác nhận site control, identity và "
            "không có bằng chứng impersonation/compromise/adverse action chưa giải quyết. Packet này "
            "không sửa source intake và không mở external scoring.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-pilot", type=Path, required=True)
    parser.add_argument("--reserve-pilot", type=Path, required=True)
    parser.add_argument("--primary-first-pass-registry", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.output_json, args.output_markdown):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")

    primary = load_json(args.primary_pilot)
    reserve = load_json(args.reserve_pilot)
    primary_first_registry = load_json(args.primary_first_pass_registry)
    if primary.get("pilot_id") != "EXTERNAL_TEXT_LEGIT_CAPTURE_PILOT_V1":
        raise ValueError("Unexpected primary pilot")
    if reserve.get("pilot_id") != "EXTERNAL_TEXT_LEGITIMATE_RESERVE_CAPTURE_V1":
        raise ValueError("Unexpected reserve pilot")
    if (
        primary_first_registry.get("analysis_id")
        != "EXTERNAL_TEXT_LEGITIMATE_AI_ASSISTED_FIRST_PASS_V1"
    ):
        raise ValueError("Unexpected primary first-pass registry")

    intake_paths = [
        _declared_output(primary, "intake_draft_v2"),
        _declared_output(reserve, "intake_draft_v1"),
    ]
    first_pass_paths = [
        _declared_output(primary_first_registry, "first_pass_records"),
        _declared_output(reserve, "ai_assisted_first_pass_v1"),
    ]
    intake_records: dict[str, dict[str, object]] = {}
    for path in intake_paths:
        for record in load_json(path).get("records", []):
            case_id = str(record.get("case_id"))
            if case_id in intake_records:
                raise ValueError(f"Duplicate intake case: {case_id}")
            intake_records[case_id] = record
    first_pass_records: dict[str, dict[str, object]] = {}
    for path in first_pass_paths:
        for record in load_json(path).get("records", []):
            case_id = str(record.get("case_id"))
            if case_id in first_pass_records:
                raise ValueError(f"Duplicate first-pass case: {case_id}")
            first_pass_records[case_id] = record
    if set(intake_records) != set(first_pass_records):
        raise ValueError("Intake and first-pass case sets differ")
    if len(intake_records) != 11:
        raise ValueError("Expected exactly eleven legitimate drafts")

    results = []
    integrity_errors = []
    for case_id in sorted(intake_records):
        record = intake_records[case_id]
        artifact = record.get("artifact", {})
        raw_path = args.raw_root / str(artifact.get("source_capture_path", ""))
        raw_valid = bool(
            raw_path.is_file()
            and sha256_file(raw_path) == artifact.get("source_capture_sha256")
        )
        text = str(artifact.get("text", ""))
        text_valid = _text_sha256(text) == artifact.get("text_sha256")
        if not raw_valid or not text_valid:
            integrity_errors.append(case_id)
        results.append(
            assess_legitimate_reconciliation_record(
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
    packet = {
        "analysis_id": "EXTERNAL_TEXT_LEGITIMATE_RECONCILIATION_PACKET_V1",
        "created_at": datetime.now().astimezone().isoformat(),
        "status": "SECOND_PASS_COMPLETE_HUMAN_DECISION_REQUIRED_ZERO_ELIGIBLE",
        "purpose": (
            "Provide a reproducible second-pass identity, registration, chronology, and "
            "contradiction review for eleven frozen legitimate-candidate drafts without labels."
        ),
        "inputs": {
            "primary_pilot": {
                "path": str(args.primary_pilot),
                "sha256": sha256_file(args.primary_pilot),
            },
            "reserve_pilot": {
                "path": str(args.reserve_pilot),
                "sha256": sha256_file(args.reserve_pilot),
            },
            "primary_first_pass_registry": {
                "path": str(args.primary_first_pass_registry),
                "sha256": sha256_file(args.primary_first_pass_registry),
            },
            "raw_root": str(args.raw_root),
            "intakes": [
                {"path": str(path), "sha256": sha256_file(path)} for path in intake_paths
            ],
            "first_pass_reports": [
                {"path": str(path), "sha256": sha256_file(path)}
                for path in first_pass_paths
            ],
        },
        "method": {
            "network_operations": 0,
            "source": "Only frozen local intake, raw capture, first-pass, and SEC/IAPD metadata.",
            "registration_semantics": (
                "Registered/APPROVED status and filed host support identity reconciliation only; "
                "they do not endorse website claims or prove absence of compromise."
            ),
            "automatic_gates": list(
                results[0]["contradiction_review"]["automatic_gate_results"].keys()
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
            "legitimate_proposal_for_human_review_count": sum(
                item["automated_second_pass"]["proposed_outcome_for_human_review"]
                == "LEGITIMATE"
                for item in results
            ),
            "high_recommendation_count": sum(
                item["automated_second_pass"]["recommendation_confidence"]
                == "HIGH_FOR_HUMAN_REVIEW"
                for item in results
            ),
            "medium_high_recommendation_count": sum(
                item["automated_second_pass"]["recommendation_confidence"]
                == "MEDIUM_HIGH_FOR_HUMAN_REVIEW"
                for item in results
            ),
            "human_decision_count": 0,
            "external_evaluation_eligible_count": 0,
            "labels_created": 0,
        },
        "manual_follow_up": {
            "case_ids": [item["case_id"] for item in results],
            "instruction": (
                "Human reviewer confirms site control and checks impersonation, compromise, "
                "misleading claims, and adverse regulator evidence before any LEGITIMATE label."
            ),
        },
        "decision_gate": {
            "hard_contradiction_case_ids": hard_cases,
            "human_confirmation_required": True,
            "promote_to_legitimate_label": False,
            "change_intake_record_state": False,
            "open_external_scoring": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "domain_access_operations": 0,
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
