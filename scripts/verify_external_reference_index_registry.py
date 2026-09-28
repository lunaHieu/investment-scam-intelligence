"""Verify one frozen external-reference registry and every pinned artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


FORBIDDEN_RECORD_KEYS = {
    "additional_information", "email", "ip_address_v4", "ip_address_v6",
    "mainaddr", "mailingaddr", "phnb", "faxnb", "postal_address", "phone_number",
    "label", "target", "prediction", "scam_probability",
}


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = {str(key).casefold() for key in value}
        for item in value.values():
            result.update(nested_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(nested_keys(item))
        return result
    return set()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    errors: list[str] = []
    artifact_results: list[dict[str, object]] = []

    input_info = registry.get("input", {})
    input_path = Path(str(input_info.get("path", "")))
    if not input_path.is_file():
        errors.append(f"missing raw input: {input_path}")
    elif sha256_file(input_path) != input_info.get("sha256"):
        errors.append("raw input SHA-256 mismatch")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"reference_index", "build_report"}:
        errors.append("output roles must be exactly reference_index and build_report")
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        if not path.is_file():
            errors.append(f"missing {role}: {path}")
            continue
        actual = sha256_file(path)
        artifact_results.append({
            "role": role,
            "path": str(path),
            "expected_sha256": item.get("sha256"),
            "actual_sha256": actual,
            "status": "MATCH" if actual == item.get("sha256") else "MISMATCH",
        })
        if actual != item.get("sha256"):
            errors.append(f"SHA-256 mismatch: {path}")

    index_info = outputs.get("reference_index", {})
    index_path = Path(str(index_info.get("path", "")))
    index_count = 0
    record_ids: set[str] = set()
    if index_path.is_file():
        with index_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"invalid JSONL at line {line_number}: {exc}")
                    break
                index_count += 1
                record_id = str(record.get("source_record_id", ""))
                if not record_id:
                    errors.append(f"missing source_record_id at line {line_number}")
                    break
                if record_id in record_ids:
                    errors.append(f"duplicate source_record_id at line {line_number}: {record_id}")
                    break
                record_ids.add(record_id)
                if record.get("source_id") != registry.get("source_id"):
                    errors.append(f"source_id mismatch at line {line_number}")
                    break
                if record.get("source_raw_sha256") != input_info.get("sha256"):
                    errors.append(f"raw provenance mismatch at line {line_number}")
                    break
                forbidden = nested_keys(record).intersection(FORBIDDEN_RECORD_KEYS)
                if forbidden:
                    errors.append(f"forbidden record keys at line {line_number}: {sorted(forbidden)}")
                    break
        if index_count != index_info.get("record_count"):
            errors.append(
                f"index record count mismatch: observed {index_count}, expected {index_info.get('record_count')}"
            )

    report_info = outputs.get("build_report", {})
    report_path = Path(str(report_info.get("path", "")))
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        source_key = "iosco" if registry.get("source_id") == "iosco_i_scan" else "sec"
        report_source = report.get("indices", {}).get(source_key, {})
        if report_source.get("record_count") != registry.get("coverage", {}).get("record_count"):
            errors.append("build report/registry record count mismatch")
        contract = report.get("output_contract", {})
        if contract.get("label_fields") != [] or contract.get("network_operations") != 0:
            errors.append("build report output contract is unsafe")

    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("registry safety counts must be zero")
    if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
        errors.append("registry safety gates must remain closed")
    if safety.get("automatic_entity_resolution_allowed") is not False:
        errors.append("automatic entity resolution must remain blocked")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "index_record_count": index_count,
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
