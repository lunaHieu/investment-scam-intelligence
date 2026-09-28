"""Prepare an offline AI-assisted first pass for SEC-linked captures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.external_text_review import assess_capture_record, extract_sec_firm_profiles
from src.isi.normalization.external_references import sha256_file


def write_brief(path: Path, result: dict[str, object]) -> None:
    comparison = result["comparison"]
    first_pass = result["ai_first_pass"]
    profile = result["sec_profile"]
    checks = comparison["contact_field_check"]
    lines = [
        f"# Review brief — {result['case_id']}",
        "",
        "## Trạng thái",
        "",
        "Record vẫn là `UNCERTAIN + LOW + IN_REVIEW`; nội dung dưới đây chỉ là AI-assisted first pass.",
        "",
        "## Đối chiếu tự động",
        "",
        f"- CRD: `{profile['crd']}`; SEC number: `{profile['sec_number']}`.",
        f"- Business name: `{profile['business_name']}`.",
        f"- Legal name: `{profile['legal_name']}`.",
        f"- SEC status: `{profile['registration'].get('FirmType')} / {profile['registration'].get('St')}`.",
        f"- Host capture có trong SEC filing: `{str(comparison['host_exactly_listed_in_sec_filing']).lower()}`.",
        f"- Full identity-token match: `{str(comparison['identity_token_check']['any_full_token_match']).lower()}`.",
        f"- Contact fields matched: `{checks['matched_count']}/{checks['available_count']}`.",
        f"- Visible text characters: `{comparison['visible_text_characters']}`.",
        "",
        "## Khuyến nghị first pass",
        "",
        f"- Identity: `{first_pass['recommended_identity_relationship']}`.",
        f"- Evidence: `{first_pass['recommended_evidence_assessment']}`.",
        f"- Outcome đề xuất để con người xem xét: `{first_pass['recommended_outcome_for_human_review']}`.",
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
    parser.add_argument("--sec-feed", required=True, type=Path)
    parser.add_argument("--intake", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--brief-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")
    intake = json.loads(args.intake.read_text(encoding="utf-8"))
    records = intake.get("records", [])
    crds = {str(record["artifact"]["source_record_id"]) for record in records}
    profiles = extract_sec_firm_profiles(args.sec_feed, crds)
    results = [
        assess_capture_record(record, profiles[str(record["artifact"]["source_record_id"])])
        for record in records
    ]
    output = {
        "analysis_id": "EXTERNAL_TEXT_LEGITIMATE_AI_ASSISTED_FIRST_PASS_V1",
        "status": "AI_ASSISTED_FIRST_PASS_HUMAN_CONFIRMATION_REQUIRED",
        "source_id": "sec_iapd",
        "inputs": {
            "sec_feed": {"path": str(args.sec_feed), "sha256": sha256_file(args.sec_feed)},
            "intake": {"path": str(args.intake), "sha256": sha256_file(args.intake)},
        },
        "records": results,
        "coverage": {
            "record_count": len(results),
            "same_entity_likely_recommendations": sum(
                item["ai_first_pass"]["recommended_identity_relationship"] == "SAME_ENTITY_LIKELY"
                for item in results
            ),
            "legitimate_recommendations_for_human_review": sum(
                item["ai_first_pass"]["recommended_outcome_for_human_review"] == "LEGITIMATE"
                for item in results
            ),
            "human_confirmed_records": 0,
            "labels_created": 0,
        },
        "safety_contract": {
            "network_operations": 0,
            "domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "raw_files_modified": False,
            "training_allowed": False,
            "domain_access_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.brief_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        write_brief(args.brief_dir / f"{result['case_id']}_review_brief_v1.md", result)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
