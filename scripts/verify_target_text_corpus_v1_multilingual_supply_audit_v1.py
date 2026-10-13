"""Independently verify the Target Text Corpus V1 multilingual supply audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(config_path: Path, report_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    report = load_object(report_path)
    errors: list[str] = []
    if report.get("report_id") != "ISI_TARGET_TEXT_CORPUS_V1_MULTILINGUAL_SUPPLY_AUDIT_REPORT_V1":
        errors.append("Unexpected multilingual audit report identity")
    if report.get("config_sha256") != sha256_file(config_path):
        errors.append("Multilingual audit config hash mismatch")
    expected_channels: list[dict[str, Any]] = []
    total_rows = unknown = 0
    for item in config["channel_inputs"]:
        rows = read_jsonl(Path(item["path"]))
        rule = item["population_filter"]
        if rule is not None:
            rows = [row for row in rows if row.get(rule["field"]) == rule["equals"]]
        counts = {"ENGLISH": 0, "VIETNAMESE": 0, "OTHER_NON_ENGLISH": 0, "UNKNOWN": 0}
        contract = config["language_evidence_contract"]
        for row in rows:
            text = row.get(contract["required_visible_text_field"])
            text_sha = row.get(contract["required_text_sha256_field"])
            language = row.get(contract["required_human_review_field"])
            if isinstance(text, str) and text.strip() and isinstance(text_sha, str) and len(text_sha) == 64 and language in contract["allowed_reviewed_languages"]:
                counts[str(language)] += 1
            else:
                counts["UNKNOWN"] += 1
        expected_channels.append({"channel_id": item["channel_id"], "audited_rows": len(rows), "counts": counts})
        total_rows += len(rows)
        unknown += counts["UNKNOWN"]
    observed_by_id = {row["channel_id"]: row for row in report.get("channels", [])}
    for expected in expected_channels:
        observed = observed_by_id.get(expected["channel_id"])
        if observed is None or observed.get("audited_rows") != expected["audited_rows"] or observed.get("reviewed_language_counts") != expected["counts"]:
            errors.append(f"Channel language counts changed: {expected['channel_id']}")
    if report.get("totals", {}).get("audited_rows") != total_rows or report.get("totals", {}).get("unknown") != unknown:
        errors.append("Multilingual audit aggregate changed")
    if unknown != total_rows:
        errors.append("Unexpected reviewed language evidence appeared")
    if report.get("decision", {}).get("language_supply_gate_met") is not False or report.get("decision", {}).get("candidate_release_allowed") is not False:
        errors.append("Multilingual audit improperly opened a gate")
    expected_safety = {"network_operations": 0, "domain_or_country_language_inferences": 0, "candidate_domain_access_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    if report.get("safety_contract") != expected_safety:
        errors.append("Multilingual audit safety contract changed")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_MULTILINGUAL_SUPPLY_AUDIT_INDEPENDENT_QA_V1",
        "status": "PASS_ALL_ROWS_UNKNOWN_LANGUAGE_GATE_CLOSED" if not errors else "FAIL",
        "inputs": {"config_sha256": sha256_file(config_path), "report_sha256": sha256_file(report_path)},
        "checks": {"channel_count": len(expected_channels), "audited_rows": total_rows, "unknown_language_rows": unknown, "verified_vietnamese_rows": 0, "verified_other_non_english_rows": 0, "language_supply_gate_met": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "captures": 0, "labels": 0, "model": 0}
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite multilingual audit QA")
    result = verify(args.config, args.report)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
