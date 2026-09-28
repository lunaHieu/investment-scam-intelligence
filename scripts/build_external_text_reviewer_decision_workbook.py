"""Build a blank, validated reviewer workbook from both reconciliation packets."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.external_text_reviewer_decisions import (
    build_pending_review_record,
)
from src.isi.normalization.external_references import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def packet_from_registry(
    registry_path: Path, expected_analysis_id: str
) -> tuple[dict[str, object], Path, str]:
    registry = load_json(registry_path)
    if registry.get("analysis_id") != expected_analysis_id:
        raise ValueError(f"Unexpected registry analysis ID: {registry_path}")
    outputs = [
        item for item in registry.get("outputs", []) if item.get("role") == "decision_packet_json"
    ]
    if len(outputs) != 1:
        raise ValueError(f"Missing unique decision_packet_json output: {registry_path}")
    path = Path(str(outputs[0].get("path", "")))
    actual_hash = sha256_file(path) if path.is_file() else None
    if actual_hash != outputs[0].get("sha256"):
        raise ValueError(f"Decision packet missing or changed: {path}")
    packet = load_json(path)
    if packet.get("analysis_id") != expected_analysis_id:
        raise ValueError(f"Packet and registry analysis IDs differ: {path}")
    if packet.get("status") != "SECOND_PASS_COMPLETE_HUMAN_DECISION_REQUIRED_ZERO_ELIGIBLE":
        raise ValueError(f"Unexpected packet status: {path}")
    return packet, path, str(actual_hash)


def review_priority(branch: str, record: dict[str, object]) -> str:
    if branch == "CONFIRMED":
        if record.get("regulator_evidence", {}).get(
            "candidate_identity_visible_in_local_capture"
        ) is True:
            return "P1_CONFIRMED_LOCAL_WARNING_IDENTITY_VISIBLE"
        return "P2_CONFIRMED_MANUAL_WARNING_FOLLOW_UP"
    if (
        record.get("automated_second_pass", {}).get("recommendation_confidence")
        == "HIGH_FOR_HUMAN_REVIEW"
    ):
        return "P3_LEGITIMATE_HIGH_ALIGNMENT"
    return "P4_LEGITIMATE_EXTRA_IDENTITY_REVIEW"


def write_markdown(path: Path, workbook: dict[str, object]) -> None:
    lines = [
        "# External-text reviewer decision workbook V1",
        "",
        "Workbook này chứa 21 form review còn trống. Nó không phải ground truth, không sửa "
        "source intake và không mở external scoring.",
        "",
        "## Thứ tự review",
        "",
        "1. `P1`: hai case CONFIRMED đã có local warning hiện đúng identity.",
        "2. `P2`: tám case CONFIRMED cần mở/kiểm tra warning thủ công.",
        "3. `P3`: sáu case LEGITIMATE có contact/identity alignment mạnh.",
        "4. `P4`: năm case LEGITIMATE cần xem thêm contact, text ngắn hoặc site control.",
        "",
        "| Priority | Case | Branch | Host | Auto proposal | Confidence | Cautions | Decision |",
        "|---|---|---|---|---|---|---|---|",
    ]
    ordered = sorted(
        workbook["records"], key=lambda item: (item["review_priority"], item["case_id"])
    )
    for record in ordered:
        context = record["automated_context"]
        cautions = ", ".join(context["caution_flags"]) or "none"
        lines.append(
            f"| `{record['review_priority']}` | `{record['case_id']}` | "
            f"`{record['branch']}` | `{record['candidate_host']}` | "
            f"`{context['proposed_outcome']}` | `{context['recommendation_confidence']}` | "
            f"{cautions} | `PENDING` |"
        )
    lines.extend(
        [
            "",
            "## Checklist CONFIRMED",
            "",
            *[
                f"- `{name}`"
                for name in next(
                    record["review_contract"]["required_checks"]
                    for record in ordered
                    if record["branch"] == "CONFIRMED"
                )
            ],
            "",
            "## Checklist LEGITIMATE",
            "",
            *[
                f"- `{name}`"
                for name in next(
                    record["review_contract"]["required_checks"]
                    for record in ordered
                    if record["branch"] == "LEGITIMATE"
                )
            ],
            "",
            "Mọi final decision, confidence, reviewer, thời điểm, rationale và confirmation source "
            "đang để trống. Dùng recorder có explicit confirmation khi review thủ công được thực hiện.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmed-registry", type=Path, required=True)
    parser.add_argument("--legitimate-registry", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.output_json, args.output_markdown):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")

    confirmed, confirmed_path, confirmed_hash = packet_from_registry(
        args.confirmed_registry, "EXTERNAL_TEXT_CONFIRMED_RECONCILIATION_PACKET_V1"
    )
    legitimate, legitimate_path, legitimate_hash = packet_from_registry(
        args.legitimate_registry, "EXTERNAL_TEXT_LEGITIMATE_RECONCILIATION_PACKET_V1"
    )
    records = []
    for branch, packet, packet_path, packet_hash in (
        ("CONFIRMED", confirmed, confirmed_path, confirmed_hash),
        ("LEGITIMATE", legitimate, legitimate_path, legitimate_hash),
    ):
        for source in packet.get("records", []):
            form = build_pending_review_record(
                source,
                branch=branch,
                packet_analysis_id=str(packet["analysis_id"]),
                packet_sha256=packet_hash,
            )
            form["source_packet"]["path"] = str(packet_path)
            form["review_priority"] = review_priority(branch, source)
            records.append(form)
    if len(records) != 21 or len({item["case_id"] for item in records}) != 21:
        raise ValueError("Expected 21 unique review forms")
    records.sort(key=lambda item: (item["review_priority"], item["case_id"]))
    priority_counts = Counter(item["review_priority"] for item in records)
    workbook = {
        "workbook_id": "EXTERNAL_TEXT_REVIEWER_DECISION_WORKBOOK_V1",
        "created_at": datetime.now().astimezone().isoformat(),
        "status": "TWENTY_ONE_PENDING_HUMAN_REVIEWS_ZERO_DECISIONS_ZERO_ELIGIBLE",
        "purpose": (
            "Provide a controlled, auditable place to record later human decisions for all "
            "confirmed and legitimate external-text drafts without mutating source intake."
        ),
        "inputs": {
            "confirmed_registry": {
                "path": str(args.confirmed_registry),
                "sha256": sha256_file(args.confirmed_registry),
            },
            "confirmed_packet": {
                "path": str(confirmed_path),
                "sha256": confirmed_hash,
            },
            "legitimate_registry": {
                "path": str(args.legitimate_registry),
                "sha256": sha256_file(args.legitimate_registry),
            },
            "legitimate_packet": {
                "path": str(legitimate_path),
                "sha256": legitimate_hash,
            },
        },
        "review_policy": {
            "allowed_final_decisions_by_branch": {
                "CONFIRMED": ["CONFIRMED", "UNCERTAIN"],
                "LEGITIMATE": ["LEGITIMATE", "UNCERTAIN"],
            },
            "target_decision_requires_high_confidence_for_materialization": True,
            "all_branch_checks_and_explicit_human_confirmation_required": True,
            "completed_review_does_not_directly_mutate_intake": True,
            "separate_reconciled_intake_materialization_required": True,
        },
        "records": records,
        "coverage": {
            "record_count": 21,
            "confirmed_branch_count": 10,
            "legitimate_branch_count": 11,
            "priority_counts": dict(sorted(priority_counts.items())),
            "pending_review_count": 21,
            "completed_review_count": 0,
            "ready_for_reconciled_intake_count": 0,
            "labels_created": 0,
            "external_evaluation_eligible_count": 0,
        },
        "decision_gate": {
            "materialize_reconciled_intake": False,
            "open_external_scoring": False,
            "reason": "No human decision has been recorded.",
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "source_intake_files_modified": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(workbook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(args.output_markdown, workbook)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_json_sha256": sha256_file(args.output_json),
                "output_markdown": str(args.output_markdown),
                "output_markdown_sha256": sha256_file(args.output_markdown),
                "coverage": workbook["coverage"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
