"""Audit whether current local assets can support frozen external text evaluation.

The audit is offline and read-only. It does not score the model, open candidate
URLs, create labels, or modify any source/review file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from mendeley_text_baseline_v2_common import MODEL_ID, sha256_file


ANALYSIS_ID = "ISI_TEXT_BASELINE_V2_EXTERNAL_EVAL_READINESS_V1"
POLICY_ID = "ISI_TEXT_BASELINE_V2_EXTERNAL_EVAL_POLICY_V1"
STATUS = "FROZEN_BLOCKED_NO_ELIGIBLE_EXTERNAL_TEXT_CASES"
EXPECTED_MODEL_SHA256 = "c58444996e0ae67a9739c588e3d088f1f57eb1af7f9105e10a647303ce72fc71"
REPORT_NAME = "external_evaluation_readiness_report_v1.json"
TEXT_FIELDS = ("text", "content", "html", "ocr_text", "page_text", "body")

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _column_index(cell_reference: str) -> int:
    match = re.match(r"([A-Z]+)", cell_reference.upper())
    if not match:
        raise ValueError(f"Invalid XLSX cell reference: {cell_reference}")
    value = 0
    for character in match.group(1):
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        values.append("".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")))
    return values


def _worksheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationship_id = None
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            relationship_id = sheet.attrib.get(f"{{{REL_NS}}}id")
            break
    if not relationship_id:
        raise ValueError(f"Worksheet not found: {sheet_name}")
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib["Target"].lstrip("/")
            if target.startswith("xl/"):
                return target
            return str(PurePosixPath("xl") / target)
    raise ValueError(f"Worksheet relationship missing: {sheet_name}")


def read_xlsx_rows(path: Path, sheet_name: str) -> list[list[object]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        root = ET.fromstring(archive.read(_worksheet_path(archive, sheet_name)))
    rows = []
    for row in root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"):
        values: list[object] = []
        for cell in row.findall(f"{{{MAIN_NS}}}c"):
            index = _column_index(cell.attrib.get("r", ""))
            while len(values) <= index:
                values.append(None)
            cell_type = cell.attrib.get("t")
            if cell_type == "inlineStr":
                value: object = "".join(
                    node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t")
                )
            else:
                node = cell.find(f"{{{MAIN_NS}}}v")
                raw = node.text if node is not None else None
                if raw is None:
                    value = None
                elif cell_type == "s":
                    value = shared[int(raw)]
                elif cell_type == "b":
                    value = raw == "1"
                elif cell_type in {"str", "e"}:
                    value = raw
                else:
                    number = float(raw)
                    value = int(number) if number.is_integer() else number
            values[index] = value
        rows.append(values)
    return rows


def table_records(rows: list[list[object]]) -> list[dict[str, object]]:
    nonempty = [row for row in rows if any(value not in (None, "") for value in row)]
    if not nonempty:
        return []
    headers = [str(value or "").strip() for value in nonempty[0]]
    if len(headers) != len(set(headers)) or any(not header for header in headers):
        raise ValueError("Workbook table header contains blank or duplicate names")
    records = []
    for row in nonempty[1:]:
        padded = row + [None] * (len(headers) - len(row))
        record = dict(zip(headers, padded[: len(headers)]))
        if any(value not in (None, "") for value in record.values()):
            records.append(record)
    return records


def profile_crimson_raw(records: list[dict]) -> dict:
    if not isinstance(records, list):
        raise ValueError("Crimson raw JSON must be a list")
    field_names = sorted({key for record in records for key in record})
    observed_text_rows = sum(
        any(isinstance(record.get(field), str) and record[field].strip() for field in TEXT_FIELDS)
        for record in records
    )
    return {
        "row_count": len(records),
        "top_level_fields": field_names,
        "recognized_observed_text_fields": [field for field in TEXT_FIELDS if field in field_names],
        "rows_with_observed_text": observed_text_rows,
    }


def profile_crimson_review(records: list[dict[str, object]]) -> dict:
    required = {
        "queue_id",
        "artifact_id",
        "domain",
        "url_canonical",
        "review_status",
        "ground_truth_status",
        "evidence_url_1",
        "evidence_url_2",
        "review_rationale",
        "review_gate",
    }
    if records and not required.issubset(records[0]):
        raise ValueError("Crimson review workbook is missing required columns")
    status_counts = Counter(str(record.get("review_status") or "") for record in records)
    return {
        "row_count": len(records),
        "review_status_counts": dict(sorted(status_counts.items())),
        "ground_truth_status_populated": sum(
            bool(str(record.get("ground_truth_status") or "").strip()) for record in records
        ),
        "evidence_url_populated": sum(
            bool(str(record.get("evidence_url_1") or "").strip())
            or bool(str(record.get("evidence_url_2") or "").strip())
            for record in records
        ),
        "review_rationale_populated": sum(
            bool(str(record.get("review_rationale") or "").strip()) for record in records
        ),
        "reconciled_rows": status_counts.get("RECONCILED", 0),
        "observed_text_rows": 0,
        "note": "The workbook contains URL/domain candidates and no observed-content text column.",
    }


def profile_ubcknn(batch: dict) -> dict:
    artifacts = batch.get("warning_artifacts", [])
    cases = batch.get("cases", [])
    return {
        "warning_artifact_count": len(artifacts),
        "warning_artifacts_with_observed_text": sum(
            bool(item.get("has_text"))
            and isinstance(item.get("text"), str)
            and bool(item["text"].strip())
            for item in artifacts
        ),
        "warning_document_count": sum(
            item.get("artifact_type") == "WARNING_DOCUMENT" for item in artifacts
        ),
        "case_status_counts": dict(
            sorted(Counter(item.get("ground_truth_status") for item in cases).items())
        ),
        "eligible_external_text_records": 0,
        "exclusion_reason": "Warning documents are evidence, not solicitation-content artifacts; all five have no observed text and remain UNCERTAIN.",
    }


def count_files(path: Path) -> int:
    return sum(item.is_file() for item in path.rglob("*")) if path.is_dir() else 0


def assess_reporting_gate(policy: dict, confirmed: int, legitimate: int) -> dict:
    gate = policy["pilot_reporting_gate"]
    total = confirmed + legitimate
    checks = {
        "minimum_total_eligible_records_met": total
        >= gate["minimum_total_eligible_records"],
        "minimum_confirmed_records_met": confirmed
        >= gate["minimum_confirmed_records"],
        "minimum_legitimate_records_met": legitimate
        >= gate["minimum_legitimate_records"],
    }
    return {
        "eligible_total": total,
        "eligible_confirmed": confirmed,
        "eligible_legitimate": legitimate,
        "requirements": gate,
        "checks": checks,
        "reporting_allowed": all(checks.values()),
    }


def prepare_output(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def audit_readiness(
    *,
    policy_path: Path,
    model_path: Path,
    crimson_raw_path: Path,
    crimson_review_path: Path,
    ubcknn_pilot_path: Path,
    dfpi_template_path: Path,
    raw_root: Path,
    output_path: Path,
    run_at: str,
    overwrite: bool = False,
) -> dict:
    inputs = {
        "policy": policy_path,
        "model": model_path,
        "crimson_raw": crimson_raw_path,
        "crimson_review_workbook": crimson_review_path,
        "ubcknn_pilot": ubcknn_pilot_path,
        "dfpi_template": dfpi_template_path,
    }
    for role, path in inputs.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing {role}: {path}")
    observed_hashes = {role: sha256_file(path) for role, path in inputs.items()}
    if observed_hashes["model"] != EXPECTED_MODEL_SHA256:
        raise ValueError("Frozen model SHA-256 mismatch")

    policy = load_json(policy_path)
    if policy.get("policy_id") != POLICY_ID:
        raise ValueError("Unexpected external-evaluation policy")
    if policy.get("status") != "FROZEN_BEFORE_EXTERNAL_TEXT_EVALUATION":
        raise ValueError("External-evaluation policy is not frozen")
    if policy.get("model_id") != MODEL_ID:
        raise ValueError("Policy model_id mismatch")

    crimson_raw = profile_crimson_raw(load_json(crimson_raw_path))
    crimson_review = profile_crimson_review(
        table_records(read_xlsx_rows(crimson_review_path, "Review queue"))
    )
    ubcknn = profile_ubcknn(load_json(ubcknn_pilot_path))
    dfpi_template = load_json(dfpi_template_path)
    raw_source_file_counts = {
        source: count_files(raw_root / source)
        for source in ("dfpi_crypto_scam_tracker", "sec_iapd", "iosco_i_scan", "ubcknn_warnings")
    }

    confirmed = 0
    legitimate = 0
    reporting_gate = assess_reporting_gate(policy, confirmed, legitimate)
    blockers = [
        "Crimson raw contains URL/network/IOC fields but no stored website text or OCR text.",
        "All 100 Crimson review rows are unreviewed and contain no evidence or ground-truth status.",
        "UBCKNN records are warning documents with no observed solicitation text and remain UNCERTAIN.",
        "DFPI intake is still a template and no DFPI raw file is present.",
        "No SEC IAPD raw reference file is present for legitimate-entity corroboration.",
        "The predeclared pilot minimum of 10 CONFIRMED and 10 LEGITIMATE reconciled text artifacts is not met.",
    ]
    quality_gates = {
        "policy_is_frozen": True,
        "model_hash_matches_frozen_v2": observed_hashes["model"]
        == EXPECTED_MODEL_SHA256,
        "crimson_raw_row_count_is_43572": crimson_raw["row_count"] == 43_572,
        "crimson_review_queue_has_100_rows": crimson_review["row_count"] == 100,
        "crimson_review_status_counts_cover_all_rows": sum(
            crimson_review["review_status_counts"].values()
        )
        == crimson_review["row_count"],
        "ubcknn_artifact_case_counts_match": ubcknn["warning_artifact_count"]
        == sum(ubcknn["case_status_counts"].values()),
        "no_model_scoring_performed": True,
        "no_candidate_url_access_performed": True,
    }
    failed = sorted(name for name, passed in quality_gates.items() if not passed)
    if failed:
        raise ValueError("Readiness quality gates failed: " + ", ".join(failed))

    report = {
        "analysis_id": ANALYSIS_ID,
        "run_at": run_at,
        "status": STATUS,
        "model_id": MODEL_ID,
        "policy_id": POLICY_ID,
        "purpose": "Determine whether current local assets can support a valid frozen external text pilot.",
        "inputs": {
            role: {"file_name": path.name, "sha256": observed_hashes[role]}
            for role, path in inputs.items()
        },
        "candidate_source_profiles": {
            "crimson_raw": crimson_raw,
            "crimson_review_workbook": crimson_review,
            "ubcknn_pilot": ubcknn,
            "dfpi_intake": {
                "status": dfpi_template.get("status"),
                "record_count": len(dfpi_template.get("records", [])),
                "eligible_external_text_records": 0,
                "raw_file_count": raw_source_file_counts[
                    "dfpi_crypto_scam_tracker"
                ],
            },
            "sec_iapd": {
                "raw_file_count": raw_source_file_counts["sec_iapd"],
                "eligible_external_text_records": 0,
                "role": "legitimate entity reference only; not a content-safety label",
            },
            "iosco_i_scan": {
                "raw_file_count": raw_source_file_counts["iosco_i_scan"],
                "eligible_external_text_records": 0,
            },
            "ubcknn_raw_folder": {
                "raw_file_count": raw_source_file_counts["ubcknn_warnings"]
            },
        },
        "reporting_gate": reporting_gate,
        "blockers": blockers,
        "decision": {
            "external_text_scoring_performed": False,
            "external_metrics_reported": False,
            "model_configuration_changed": False,
            "reason": "There are zero eligible, evidence-backed, reconciled external text artifacts and neither class meets the frozen pilot minimum.",
            "next_action": "Acquire or curate observed POST, MESSAGE, or WEBSITE_SNAPSHOT text; reconcile evidence; then re-run this gate before scoring the unchanged model.",
        },
        "quality_gates": quality_gates,
        "safety_contract": {
            "raw_files_modified": False,
            "review_workbook_modified": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "model_fit_operations": 0,
            "network_operations": 0,
            "candidate_url_access_operations": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
            "deployment_allowed": False,
        },
    }
    prepare_output(output_path, overwrite)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--crimson-raw", type=Path, required=True)
    parser.add_argument("--crimson-review", type=Path, required=True)
    parser.add_argument("--ubcknn-pilot", type=Path, required=True)
    parser.add_argument("--dfpi-template", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-at", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = audit_readiness(
        policy_path=args.policy,
        model_path=args.model,
        crimson_raw_path=args.crimson_raw,
        crimson_review_path=args.crimson_review,
        ubcknn_pilot_path=args.ubcknn_pilot,
        dfpi_template_path=args.dfpi_template,
        raw_root=args.raw_root,
        output_path=args.output,
        run_at=args.run_at or datetime.now(timezone.utc).isoformat(),
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "analysis_id": report["analysis_id"],
                "status": report["status"],
                "reporting_gate": report["reporting_gate"],
                "decision": report["decision"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
