"""Verify the frozen Mendeley image-readiness report and registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    errors: list[str] = []

    input_info = registry.get("input", {})
    input_path = Path(input_info.get("csv_path", ""))
    if not input_path.is_file():
        errors.append(f"Missing CSV input: {input_path}")
    elif sha256_file(input_path) != input_info.get("csv_sha256"):
        errors.append("CSV SHA-256 does not match registry")

    outputs = registry.get("outputs", [])
    if len(outputs) != 1 or outputs[0].get("role") != "image_readiness_report":
        errors.append("Registry must declare exactly one image_readiness_report output")
        report = {}
    else:
        report_path = Path(outputs[0].get("path", ""))
        if not report_path.is_file():
            errors.append(f"Missing report: {report_path}")
            report = {}
        else:
            if sha256_file(report_path) != outputs[0].get("sha256"):
                errors.append("Report SHA-256 does not match registry")
            report = load_json(report_path)

    decision = registry.get("decision", {})
    report_decision = report.get("decision", {})
    if decision.get("has_usable_image_assets") is not False:
        errors.append("Registry image asset gate must remain closed")
    if decision.get("image_model_training_allowed") is not False:
        errors.append("Registry image training gate must remain closed")
    if report_decision.get("status") != "BLOCKED_NO_IMAGE_ASSETS":
        errors.append("Report does not record BLOCKED_NO_IMAGE_ASSETS")
    if report_decision.get("image_model_training_allowed") is not False:
        errors.append("Report image training gate is open")

    findings = registry.get("findings", {})
    report_profile = report.get("csv_profile", {})
    if input_info.get("record_count") != report_profile.get("record_count"):
        errors.append("Record count differs between registry and report")
    if input_info.get("column_count") != report_profile.get("column_count"):
        errors.append("Column count differs between registry and report")
    if findings.get("actual_image_reference_count") != sum(
        report_profile.get("actual_image_reference_count_by_column", {}).values()
    ):
        errors.append("Image reference count differs between registry and report")
    if findings.get("raw_folder_image_file_count") != report.get("raw_folder_image_file_count"):
        errors.append("Raw-folder image count differs between registry and report")
    if findings.get("xlsx_embedded_media_entry_count") != report.get("xlsx_profile", {}).get(
        "embedded_media_entry_count"
    ):
        errors.append("XLSX media count differs between registry and report")

    safety = report.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("Report must record zero network operations and zero labels")
    if safety.get("raw_files_modified") is not False:
        errors.append("Report must state that raw files were not modified")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "csv_sha256": sha256_file(input_path) if input_path.is_file() else None,
        "report_sha256": sha256_file(Path(outputs[0]["path"])) if outputs and Path(outputs[0]["path"]).is_file() else None,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
