"""Verify C2 tooling or a real external artifact/rights submission offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from scripts.prepare_target_text_corpus_v1_c2_external_artifact_intake_v1 import _json_bytes, _resolve, prepare
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_INTAKE_PROTOCOL_V1"
TOP_FIELDS = {"submission_id", "protocol_id", "status", "created_at", "prepared_by", "items"}
ITEM_FIELDS = {"item_id", "item_type", "source_id", "official_source_url", "acquisition_mode", "acquired_at", "original_filename", "stored_relative_path", "media_type", "byte_size", "sha256", "rights_basis", "prerequisite_rights_registry_path", "redistribution_permitted", "contains_personal_data", "notes"}
RIGHTS_FIELDS = {"basis_type", "terms_or_permission_url", "summary"}


def _valid_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def verify_tooling(config_path: Path, template_path: Path, report_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        prepared = prepare(config_path)
    except (KeyError, OSError, ValueError) as exc:
        return _tooling_result(config_path, template_path, report_path, [str(exc)])
    config = prepared["config"]
    outputs = config["planned_outputs"]
    if Path(outputs["submission_template"]).resolve() != template_path.resolve() or Path(outputs["preparation_report"]).resolve() != report_path.resolve():
        errors.append("C2 template/report paths differ from the frozen protocol")
    template = load_object(template_path)
    if template != prepared["template"] or template.get("status") != "TEMPLATE_NOT_A_SUBMISSION":
        errors.append("C2 template differs from recomputation or can be confused with a submission")
    root = config_path.resolve().parents[1]
    schema_item = next(item for item in config["inputs"] if item["role"] == "submission_schema")
    schema = load_object(_resolve(root, schema_item["path"]))
    properties = schema.get("properties", {})
    item_schema = properties.get("items", {}).get("items", {})
    if schema.get("additionalProperties") is not False or set(schema.get("required", [])) != set(properties):
        errors.append("C2 schema does not enforce exact top-level fields")
    if properties.get("items", {}).get("maxItems") != config["storage_contract"]["maximum_items_per_submission"] or item_schema.get("additionalProperties") is not False:
        errors.append("C2 schema does not enforce bounded exact items")
    if properties.get("protocol_id", {}).get("const") != EXPECTED_PROTOCOL_ID or properties.get("status", {}).get("const") != "PENDING_INDEPENDENT_C2_INTAKE_QA":
        errors.append("C2 schema is not bound to the frozen protocol/status")
    if item_schema.get("properties", {}).get("redistribution_permitted", {}).get("const") is not False:
        errors.append("C2 schema permits redistribution")
    report = load_object(report_path)
    if report.get("status") != "PASS_C2_INTAKE_TEMPLATE_PREPARED_EXTERNAL_INPUTS_ABSENT" or report.get("protocol_sha256") != sha256_file(config_path) or report.get("template_sha256") != hashlib.sha256(_json_bytes(prepared["template"])).hexdigest():
        errors.append("C2 preparation report binding mismatch")
    if report.get("source_contracts") != 4 or report.get("decision", {}).get("completed_submission_exists") is not False:
        errors.append("C2 preparation report source/gate state mismatch")
    for key in ("completed_submission", "independent_submission_qa", "versioned_readiness_ledger"):
        path = Path(outputs[key])
        if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
            errors.append(f"Future C2 output exists without a submitted external input: {key}")
    return _tooling_result(config_path, template_path, report_path, errors)


def _tooling_result(config_path: Path, template_path: Path, report_path: Path, errors: list[str]) -> dict[str, Any]:
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_INTAKE_TOOLING_QA_V1",
        "status": "PASS_C2_PREFLIGHT_FOUR_SOURCE_INTAKE_READY_EXTERNAL_INPUTS_ABSENT" if not errors else "FAIL",
        "inputs": {
            "protocol_sha256": sha256_file(config_path),
            "template_sha256": sha256_file(template_path) if template_path.is_file() else None,
            "preparation_report_sha256": sha256_file(report_path) if report_path.is_file() else None,
        },
        "checks": {"source_contracts": 4, "completed_submission_files": 0 if not errors else None},
        "decision": {"c2_preflight_complete": not errors, "c2_intake_complete": False, "candidate_enumeration_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "source_files_acquired": 0, "rights_records_acquired": 0, "labels_changed": 0, "model_operations": 0},
    }


def validate_submission(config_path: Path, submission_path: Path, data_root: Path) -> dict[str, Any]:
    prepared = prepare(config_path)
    config = prepared["config"]
    if data_root.resolve() != Path(config["storage_contract"]["data_root"]).resolve():
        raise ValueError("C2 data root differs from the frozen storage contract")
    submission = load_object(submission_path)
    if set(submission) != TOP_FIELDS:
        raise ValueError("C2 submission top-level fields differ from schema")
    if submission.get("protocol_id") != EXPECTED_PROTOCOL_ID or submission.get("status") != "PENDING_INDEPENDENT_C2_INTAKE_QA":
        raise ValueError("C2 submission is not bound to the frozen protocol/status")
    if not isinstance(submission.get("submission_id"), str) or not submission["submission_id"] or not isinstance(submission.get("prepared_by"), str) or not submission["prepared_by"]:
        raise ValueError("C2 submission identity/preparer is missing")
    if not _valid_datetime(submission.get("created_at")):
        raise ValueError("C2 submission created_at must include a timezone")
    items = submission.get("items")
    limit = config["storage_contract"]["maximum_items_per_submission"]
    if not isinstance(items, list) or not items or len(items) > limit:
        raise ValueError(f"C2 submission must contain 1-{limit} items")
    contracts = {item["source_id"]: item for item in config["source_contracts"]}
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    source_counts: dict[str, int] = {}
    type_counts = {"SOURCE_ARTIFACT": 0, "RIGHTS_EVIDENCE_RECORD": 0}
    for item in items:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            raise ValueError("C2 submission item fields differ from schema")
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in seen_ids:
            raise ValueError("C2 item IDs must be non-empty and unique")
        seen_ids.add(item_id)
        source_id = item.get("source_id")
        if source_id not in contracts:
            raise ValueError(f"Unknown C2 source ID: {source_id}")
        contract = contracts[source_id]
        item_type = item.get("item_type")
        if item_type not in type_counts:
            raise ValueError(f"Unknown C2 item type: {item_type}")
        if item_type == "SOURCE_ARTIFACT" and contract["artifact_phase"] != "ARTIFACT_OR_RIGHTS_RECORD_MAY_ENTER_QA":
            raise ValueError(f"Source artifact remains blocked pending a separate rights-readiness ledger: {source_id}")
        allowed_modes = contract["allowed_source_artifact_modes"] if item_type == "SOURCE_ARTIFACT" else contract["allowed_rights_record_modes"]
        if item.get("acquisition_mode") not in allowed_modes:
            raise ValueError(f"C2 acquisition mode is not allowed: {item_id}")
        parsed = urlparse(str(item.get("official_source_url", "")))
        if parsed.scheme != "https" or parsed.hostname not in contract["allowed_hosts"]:
            raise ValueError(f"C2 URL is outside the official host allowlist: {item_id}")
        rights = item.get("rights_basis")
        if not isinstance(rights, dict) or set(rights) != RIGHTS_FIELDS or rights.get("basis_type") not in contract["allowed_rights_basis_types"] or not isinstance(rights.get("summary"), str) or not rights["summary"].strip():
            raise ValueError(f"C2 rights basis is incomplete or unsupported: {item_id}")
        if not _valid_datetime(item.get("acquired_at")):
            raise ValueError(f"C2 acquired_at must include a timezone: {item_id}")
        if item.get("redistribution_permitted") is not False or not isinstance(item.get("contains_personal_data"), bool):
            raise ValueError(f"C2 redistribution/privacy flags are invalid: {item_id}")
        relative = str(item.get("stored_relative_path", ""))
        posix = PurePosixPath(relative.replace("\\", "/"))
        if posix.is_absolute() or ".." in posix.parts or not posix.parts:
            raise ValueError(f"Unsafe C2 stored path: {item_id}")
        expected_directory = PurePosixPath(contract["source_artifact_relative_directory"] if item_type == "SOURCE_ARTIFACT" else contract["rights_evidence_relative_directory"])
        if tuple(posix.parts[: len(expected_directory.parts)]) != expected_directory.parts:
            raise ValueError(f"C2 stored path is outside the source/type directory: {item_id}")
        normalized = posix.as_posix()
        if normalized in seen_paths:
            raise ValueError(f"Duplicate C2 stored path: {normalized}")
        seen_paths.add(normalized)
        artifact = data_root.joinpath(*posix.parts)
        if not artifact.is_file():
            raise ValueError(f"C2 submitted file is missing: {normalized}")
        if not isinstance(item.get("byte_size"), int) or item["byte_size"] < 1 or artifact.stat().st_size != item["byte_size"]:
            raise ValueError(f"C2 submitted byte size mismatch: {normalized}")
        expected_hash = item.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or expected_hash.lower() != expected_hash or sha256_file(artifact) != expected_hash:
            raise ValueError(f"C2 submitted SHA-256 mismatch: {normalized}")
        type_counts[item_type] += 1
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_SUBMISSION_QA_V1",
        "status": "PASS_C2_SUBMISSION_BYTES_HASHES_SOURCE_AND_RIGHTS_RECOMPUTED",
        "submission_id": submission["submission_id"],
        "submission_sha256": sha256_file(submission_path),
        "item_count": len(items),
        "source_counts": dict(sorted(source_counts.items())),
        "type_counts": type_counts,
        "decision": {"intake_qa_passed": True, "new_versioned_readiness_ledger_required": True, "candidate_enumeration_allowed": False, "labels_created": 0, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "candidate_records_enumerated": 0, "labels_changed": 0, "model_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.submission) != bool(args.data_root):
        parser.error("--submission and --data-root must be provided together")
    if args.submission:
        result = validate_submission(args.config, args.submission, args.data_root)
    else:
        if not args.template or not args.report:
            parser.error("--template and --report are required for tooling QA")
        result = verify_tooling(args.config, args.template, args.report)
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite C2 QA")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status", "").startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
