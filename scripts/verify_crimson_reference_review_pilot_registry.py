"""Verify the frozen Crimson reference-review pilot, workbook, and safety state."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def inspect_xlsx(path: Path) -> dict[str, object]:
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet_names = [element.attrib["name"] for element in workbook_xml.findall(".//m:sheet", namespace)]
        formula_count = 0
        validation_count = 0
        for name in names:
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            root = ET.fromstring(archive.read(name))
            formula_count += len(root.findall(".//m:f", namespace))
            validation_count += len(root.findall(".//m:dataValidation", namespace))
    return {
        "sheet_names": sheet_names,
        "formula_count": formula_count,
        "data_validation_count": validation_count,
        "contains_vba_project": "xl/vbaProject.bin" in names,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    errors: list[str] = []
    artifact_results: list[dict[str, object]] = []
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    required_roles = {"pilot_records", "evidence_records", "selection_report", "review_workbook"}
    if set(outputs) != required_roles:
        errors.append("output roles do not match the frozen pilot contract")

    paths: dict[str, Path] = {}
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        paths[role] = path
        if not path.is_file():
            errors.append(f"missing output {role}: {path}")
            continue
        actual = sha256_file(path)
        artifact_results.append({
            "role": role, "path": str(path), "expected_sha256": item.get("sha256"),
            "actual_sha256": actual, "status": "MATCH" if actual == item.get("sha256") else "MISMATCH",
        })
        if actual != item.get("sha256"):
            errors.append(f"SHA-256 mismatch: {role}")

    pilot_records = load_jsonl(paths["pilot_records"]) if paths.get("pilot_records", Path()).is_file() else []
    evidence_records = load_jsonl(paths["evidence_records"]) if paths.get("evidence_records", Path()).is_file() else []
    if len(pilot_records) != outputs.get("pilot_records", {}).get("record_count"):
        errors.append("pilot record count mismatch")
    if len(evidence_records) != outputs.get("evidence_records", {}).get("record_count"):
        errors.append("evidence record count mismatch")
    if len({record.get("pilot_id") for record in pilot_records}) != len(pilot_records):
        errors.append("pilot IDs are not unique")
    if sorted(record.get("pilot_rank") for record in pilot_records) != list(range(1, len(pilot_records) + 1)):
        errors.append("pilot ranks are not a complete sequence")
    status_counts = Counter(str(record.get("review_status")) for record in pilot_records)
    if status_counts != Counter({"NOT_STARTED": 40}):
        errors.append("pilot is no longer in the frozen unreviewed state")
    if any(record.get("training_eligible") != "NO" or record.get("label_created") is not False for record in pilot_records):
        errors.append("pilot contains a training-eligible or labeled record")
    if any(record.get("review_status") != "UNREVIEWED" or record.get("label_created") is not False for record in evidence_records):
        errors.append("evidence records are no longer frozen and unlabeled")

    report_path = paths.get("selection_report")
    if report_path and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("selection_bucket_counts") != registry.get("selection_protocol", {}).get("strata"):
            errors.append("selection report/registry stratum mismatch")
        if report.get("pilot_record_count") != len(pilot_records) or report.get("evidence_record_count") != len(evidence_records):
            errors.append("selection report output counts mismatch")

    workbook_profile: dict[str, object] = {}
    workbook_path = paths.get("review_workbook")
    if workbook_path and workbook_path.is_file():
        workbook_profile = inspect_xlsx(workbook_path)
        if workbook_profile["sheet_names"] != ["Review", "Review plan", "Evidence", "Guide"]:
            errors.append("workbook sheet names/order mismatch")
        if int(workbook_profile["formula_count"]) < 85:
            errors.append("workbook is missing expected workflow formulas")
        if int(workbook_profile["data_validation_count"]) < 5:
            errors.append("workbook is missing expected review dropdowns")
        if workbook_profile["contains_vba_project"]:
            errors.append("review workbook must not contain VBA")

    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("safety counts must remain zero")
    if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
        errors.append("training/domain-access gates must remain closed")

    result = {
        "pilot_id": registry.get("pilot_id"),
        "status": "VALID" if not errors else "INVALID",
        "pilot_record_count": len(pilot_records),
        "evidence_record_count": len(evidence_records),
        "workbook_profile": workbook_profile,
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
