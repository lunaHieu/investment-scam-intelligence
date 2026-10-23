"""Independently verify C3 exact-42 language-response tooling and pending template."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.prepare_target_text_corpus_v1_a5_language_review_response_v1 import _json_bytes, prepare
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(config_path: Path, template_path: Path, report_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        prepared = prepare(config_path)
    except (KeyError, OSError, ValueError) as exc:
        return _result(config_path, template_path, report_path, 0, [str(exc)])
    config = prepared["config"]
    outputs = config["planned_outputs"]
    if Path(outputs["response_template"]).resolve() != template_path.resolve() or Path(outputs["preparation_report"]).resolve() != report_path.resolve():
        errors.append("C3 template/report paths differ from the frozen protocol")
    expected_template = prepared["template"]
    template = load_object(template_path)
    if template != expected_template:
        errors.append("C3 response template differs from full offline recomputation")
    if template.get("status") != "TEMPLATE_NOT_A_COMPLETED_RESPONSE":
        errors.append("C3 template can be confused with a completed response")
    reviewer = template.get("reviewer", {})
    if reviewer.get("reviewer_type") is not None or reviewer.get("independent_human_attestation") is not False:
        errors.append("C3 template prefilled or fabricated a human attestation")
    records = template.get("records", [])
    if any(row.get("language_code") is not None or row.get("human_reviewed_language") is not False for row in records):
        errors.append("C3 template prefilled a language decision")

    root = config_path.resolve().parents[1]
    schema_input = next(item for item in config["inputs"] if item["role"] == "response_schema")
    schema_path = Path(schema_input["path"])
    if not schema_path.is_absolute():
        schema_path = root / schema_path
    schema = load_object(schema_path)
    properties = schema.get("properties", {})
    record_schema = properties.get("records", {})
    reviewer_schema = properties.get("reviewer", {}).get("properties", {})
    if schema.get("additionalProperties") is not False or set(schema.get("required", [])) != set(properties):
        errors.append("C3 response schema does not enforce exact top-level fields")
    if record_schema.get("minItems") != 42 or record_schema.get("maxItems") != 42 or record_schema.get("items", {}).get("additionalProperties") is not False:
        errors.append("C3 response schema does not enforce exact-42 rows")
    if reviewer_schema.get("reviewer_type", {}).get("const") != "HUMAN" or reviewer_schema.get("automatic_or_ai_hint_used_as_final", {}).get("const") is not False:
        errors.append("C3 response schema weakened the human-only review contract")
    if properties.get("language_packet_sha256", {}).get("const") != config["population_contract"]["language_packet_sha256"]:
        errors.append("C3 response schema is not bound to the language packet hash")

    report = load_object(report_path)
    expected_template_hash = hashlib.sha256(_json_bytes(expected_template)).hexdigest()
    if report.get("status") != "PASS_C3_TEMPLATE_PREPARED_HUMAN_RESPONSE_ABSENT" or report.get("protocol_sha256") != sha256_file(config_path) or report.get("template_sha256") != expected_template_hash:
        errors.append("C3 preparation report binding mismatch")
    if report.get("population") != {"records": 42, "development": 33, "external_holdout": 9}:
        errors.append("C3 preparation report population mismatch")
    if report.get("review_state") != {"pending_human_review": 42, "completed_human_review": 0}:
        errors.append("C3 preparation report claims human completion")
    if report.get("decision", {}).get("human_response_exists") is not False or report.get("decision", {}).get("training_allowed") is not False:
        errors.append("C3 preparation report opened a forbidden gate")
    for key in ("completed_response", "independent_response_qa", "language_supply_report"):
        path = Path(outputs[key])
        if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
            errors.append(f"Future C3 output exists before truthful human review: {key}")
    return _result(config_path, template_path, report_path, len(records), errors)


def _result(config_path: Path, template_path: Path, report_path: Path, records: int, errors: list[str]) -> dict[str, Any]:
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_A5_LANGUAGE_RESPONSE_TOOLING_QA_V1",
        "status": "PASS_C3_PREFLIGHT_EXACT_42_TEMPLATE_AND_VERIFIER_READY_HUMAN_RESPONSE_ABSENT" if not errors else "FAIL",
        "inputs": {
            "protocol_sha256": sha256_file(config_path),
            "template_sha256": sha256_file(template_path) if template_path.is_file() else None,
            "preparation_report_sha256": sha256_file(report_path) if report_path.is_file() else None,
        },
        "checks": {"template_records_recomputed": records, "completed_response_files": 0 if not errors else None},
        "decision": {
            "c3_preflight_complete": not errors,
            "c3_human_response_complete": False,
            "language_supply_credit_now": 0,
            "v1_core_admission_credit_now": 0,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "human_decisions_fabricated": 0, "labels_changed": 0, "model_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite C3 tooling QA")
    result = verify(args.config, args.template, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
