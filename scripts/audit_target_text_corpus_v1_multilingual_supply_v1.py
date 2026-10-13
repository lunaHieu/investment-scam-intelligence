"""Audit reviewed visible-text language supply without network access or labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def select_population(rows: list[dict[str, Any]], rule: dict[str, Any] | None) -> list[dict[str, Any]]:
    if rule is None:
        return rows
    selected = [row for row in rows if row.get(rule["field"]) == rule["equals"]]
    if len(selected) != rule["expected_rows"]:
        raise ValueError("Filtered language-audit population changed")
    return selected


def reviewed_language(row: dict[str, Any], contract: dict[str, Any]) -> str:
    text = row.get(contract["required_visible_text_field"])
    text_sha = row.get(contract["required_text_sha256_field"])
    language = row.get(contract["required_human_review_field"])
    if not isinstance(text, str) or not text.strip() or not isinstance(text_sha, str) or len(text_sha) != 64:
        return "UNKNOWN"
    if language not in contract["allowed_reviewed_languages"]:
        return "UNKNOWN"
    return str(language)


def validate_config(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("audit_id") != "ISI_TARGET_TEXT_CORPUS_V1_MULTILINGUAL_SUPPLY_AUDIT_V1":
        raise ValueError("Unexpected multilingual supply audit")
    root = config_path.resolve().parents[1]
    for item in config["basis"]:
        if sha256_file(root / item["path"]) != item["sha256"]:
            raise ValueError(f"Multilingual audit basis mismatch: {item['role']}")
    for item in config["channel_inputs"]:
        path = Path(item["path"])
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Multilingual audit input mismatch: {item['channel_id']}")
        rows = read_jsonl(path)
        if len(rows) != item["expected_metadata_rows"]:
            raise ValueError(f"Multilingual audit row count changed: {item['channel_id']}")
    contract = config["language_evidence_contract"]
    if contract["domain_tld_inference_allowed"] or contract["entity_country_inference_allowed"] or contract["reference_page_language_as_artifact_language_allowed"]:
        raise ValueError("Multilingual audit permits unsupported language inference")
    for gate in ("network_access_allowed", "candidate_enumeration_allowed", "artifact_capture_allowed", "language_quota_waiver_allowed", "labeling_allowed", "training_allowed"):
        if config["decision"].get(gate) is not False:
            raise PermissionError(f"Multilingual audit opened forbidden gate: {gate}")
    return config


def audit(config_path: Path) -> dict[str, Any]:
    config = validate_config(config_path)
    contract = config["language_evidence_contract"]
    channels: list[dict[str, Any]] = []
    totals = {"audited_rows": 0, "english": 0, "vietnamese": 0, "other_non_english": 0, "unknown": 0}
    by_status: dict[str, dict[str, int]] = {}
    for item in config["channel_inputs"]:
        rows = select_population(read_jsonl(Path(item["path"])), item["population_filter"])
        counts = {"ENGLISH": 0, "VIETNAMESE": 0, "OTHER_NON_ENGLISH": 0, "UNKNOWN": 0}
        for row in rows:
            counts[reviewed_language(row, contract)] += 1
        channels.append({
            "channel_id": item["channel_id"],
            "target_status": item["target_status"],
            "metadata_rows": item["expected_metadata_rows"],
            "audited_rows": len(rows),
            "reviewed_language_counts": counts,
            "verified_non_english_rows": counts["VIETNAMESE"] + counts["OTHER_NON_ENGLISH"],
            "language_supply_ready": False,
        })
        totals["audited_rows"] += len(rows)
        totals["english"] += counts["ENGLISH"]
        totals["vietnamese"] += counts["VIETNAMESE"]
        totals["other_non_english"] += counts["OTHER_NON_ENGLISH"]
        totals["unknown"] += counts["UNKNOWN"]
        status = by_status.setdefault(item["target_status"], {"verified_vietnamese": 0, "verified_other_non_english": 0, "unknown": 0})
        status["verified_vietnamese"] += counts["VIETNAMESE"]
        status["verified_other_non_english"] += counts["OTHER_NON_ENGLISH"]
        status["unknown"] += counts["UNKNOWN"]
    quota = config["quota_contract"]
    label_gate = {
        status: {
            **values,
            "minimum_vietnamese_required_across_development_and_holdout": quota["development_minimum_vietnamese_groups_per_label"] + quota["external_holdout_minimum_vietnamese_groups_per_label"],
            "minimum_non_english_required_across_development_and_holdout": quota["development_minimum_non_english_groups_per_label"] + quota["external_holdout_minimum_non_english_groups_per_label"],
            "supply_gate_met": False,
        }
        for status, values in sorted(by_status.items())
    }
    return {
        "report_id": config["planned_output"]["report_id"],
        "status": "FAIL_CLOSED_ZERO_VERIFIED_MULTILINGUAL_SUPPLY_ALL_REFERENCE_METADATA_UNKNOWN",
        "config_path": str(config_path.resolve()),
        "config_sha256": sha256_file(config_path),
        "channels": channels,
        "totals": totals,
        "label_language_gates": label_gate,
        "decision": {
            "language_supply_audited": True,
            "language_supply_gate_met": False,
            "candidate_release_allowed": False,
            "reason": "No audited pool row contains immutable observed artifact visible text, its SHA-256, and a human-reviewed language decision; all rows therefore remain UNKNOWN.",
            "next_gate": "Register a terms-reviewed Vietnamese legitimate-reference path and a balanced confirmed-language path, then capture/review fresh archived artifacts before claiming language supply."
        },
        "safety_contract": {"network_operations": 0, "domain_or_country_language_inferences": 0, "candidate_domain_access_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite multilingual supply audit")
    result = audit(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
