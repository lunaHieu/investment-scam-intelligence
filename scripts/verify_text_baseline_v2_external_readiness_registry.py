"""Verify and reproduce the frozen external-evaluation readiness audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_text_baseline_v2_external_readiness import (
    ANALYSIS_ID,
    REPORT_NAME,
    STATUS,
    audit_readiness,
)
from mendeley_text_baseline_v2_common import MODEL_ID, sha256_file


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT
        / "registry"
        / "analyses"
        / "text_baseline_v2_external_readiness_v1.json",
    )
    args = parser.parse_args()
    registry = load_json(args.registry)
    errors = []
    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis_id")
    if registry.get("status") != STATUS:
        errors.append("Readiness registry status mismatch")
    if registry.get("model_id") != MODEL_ID:
        errors.append("Readiness registry model_id mismatch")
    if registry.get("source_id") != "mendeley_investment_deceptive_2026":
        errors.append("Readiness registry source_id mismatch")

    inputs = {item.get("role"): item for item in registry.get("inputs", [])}
    expected_roles = {
        "policy",
        "model",
        "crimson_raw",
        "crimson_review_workbook",
        "ubcknn_pilot",
        "dfpi_template",
    }
    if set(inputs) != expected_roles:
        errors.append("Readiness registry input roles mismatch")
    input_paths = {}
    for role, item in inputs.items():
        path = Path(item.get("path", ""))
        input_paths[role] = path
        if not path.is_file():
            errors.append(f"Missing readiness input: {role}")
        elif sha256_file(path) != item.get("sha256"):
            errors.append(f"Readiness input hash mismatch: {role}")

    outputs = registry.get("outputs", [])
    report_path = Path(outputs[0].get("path", "")) if len(outputs) == 1 else Path()
    if len(outputs) != 1 or outputs[0].get("role") != "readiness_report":
        errors.append("Readiness registry output role mismatch")
    elif not report_path.is_file():
        errors.append("Missing readiness report")
    elif sha256_file(report_path) != outputs[0].get("sha256"):
        errors.append("Readiness report hash mismatch")

    report = load_json(report_path) if report_path.is_file() else {}
    if report:
        if report.get("status") != STATUS or report.get("analysis_id") != ANALYSIS_ID:
            errors.append("Readiness report ID/status mismatch")
        if report.get("reporting_gate", {}).get("reporting_allowed") is not False:
            errors.append("External reporting gate must remain closed")
        if report.get("reporting_gate", {}).get("eligible_total") != 0:
            errors.append("Readiness report unexpectedly has eligible records")
        if not all(report.get("quality_gates", {}).values()):
            errors.append("Readiness report contains failed quality gates")

    required_safety = {
        "labels_created": 0,
        "model_scoring_operations": 0,
        "model_fit_operations": 0,
        "network_operations": 0,
        "candidate_url_access_operations": 0,
        "training_allowed": False,
        "domain_access_allowed": False,
        "deployment_allowed": False,
    }
    for source_name, safety in (
        ("registry", registry.get("safety_contract", {})),
        ("report", report.get("safety_contract", {})),
    ):
        for key, expected in required_safety.items():
            if safety.get(key) != expected:
                errors.append(f"{source_name} safety mismatch: {key}")

    reproduced_sha256 = None
    if not errors:
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_output = Path(temp_dir) / REPORT_NAME
            reproduced = audit_readiness(
                policy_path=input_paths["policy"],
                model_path=input_paths["model"],
                crimson_raw_path=input_paths["crimson_raw"],
                crimson_review_path=input_paths["crimson_review_workbook"],
                ubcknn_pilot_path=input_paths["ubcknn_pilot"],
                dfpi_template_path=input_paths["dfpi_template"],
                raw_root=Path(registry["raw_root"]),
                output_path=temp_output,
                run_at=report["run_at"],
            )
            if reproduced["reporting_gate"] != report["reporting_gate"]:
                errors.append("Reproduced reporting gate mismatch")
            reproduced_sha256 = sha256_file(temp_output)
            if reproduced_sha256 != outputs[0]["sha256"]:
                errors.append("Readiness report bit-for-bit reproduction mismatch")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "eligible_external_text_records": report.get("reporting_gate", {}).get(
            "eligible_total"
        ),
        "reporting_allowed": report.get("reporting_gate", {}).get(
            "reporting_allowed"
        ),
        "reproduced_sha256": reproduced_sha256,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
