"""Verify and reproduce the frozen Text Baseline V2 error analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from analyze_mendeley_text_baseline_v2_errors import (
    ANALYSIS_ID,
    STATUS,
    analyze_frozen_errors,
    load_predictions,
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
        / "mendeley_text_baseline_v2_error_analysis.json",
    )
    args = parser.parse_args()
    registry = load_json(args.registry)
    errors = []

    if registry.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis_id")
    if registry.get("status") != STATUS:
        errors.append("Analysis registry is not frozen diagnostic-only")
    if registry.get("model_id") != MODEL_ID:
        errors.append("Unexpected model_id")
    if registry.get("source_id") != "mendeley_investment_deceptive_2026":
        errors.append("Unexpected source_id")

    input_entries = {item.get("role"): item for item in registry.get("inputs", [])}
    expected_input_roles = {
        "group_split_dataset",
        "model",
        "results",
        "test_predictions",
    }
    if set(input_entries) != expected_input_roles:
        errors.append("Input role set mismatch")
    input_paths = {}
    for role, entry in input_entries.items():
        path = Path(entry.get("path", ""))
        input_paths[role] = path
        if not path.is_file():
            errors.append(f"Missing input artifact: {role}")
        elif sha256_file(path) != entry.get("sha256"):
            errors.append(f"Input SHA-256 mismatch: {role}")

    output_entries = {item.get("role"): item for item in registry.get("outputs", [])}
    expected_output_roles = {"error_analysis_report", "error_review_queue"}
    if set(output_entries) != expected_output_roles:
        errors.append("Output role set mismatch")
    output_paths = {}
    for role, entry in output_entries.items():
        path = Path(entry.get("path", ""))
        output_paths[role] = path
        if not path.is_file():
            errors.append(f"Missing output artifact: {role}")
        elif sha256_file(path) != entry.get("sha256"):
            errors.append(f"Output SHA-256 mismatch: {role}")

    safety = registry.get("safety_contract", {})
    required_safety = {
        "network_operations": 0,
        "labels_created": 0,
        "training_allowed": False,
        "domain_access_allowed": False,
        "test_used_for_tuning": False,
        "deployment_allowed": False,
    }
    for key, expected in required_safety.items():
        if safety.get(key) != expected:
            errors.append(f"Safety contract mismatch: {key}")

    report = {}
    queue = []
    if output_paths.get("error_analysis_report", Path()).is_file():
        report = load_json(output_paths["error_analysis_report"])
        if report.get("analysis_id") != ANALYSIS_ID or report.get("status") != STATUS:
            errors.append("Report ID/status mismatch")
        if not all(report.get("quality_gates", {}).values()):
            errors.append("Report contains a failed quality gate")
        report_safety = report.get("safety_contract", {})
        for key, expected in required_safety.items():
            if report_safety.get(key) != expected:
                errors.append(f"Report safety contract mismatch: {key}")
    if output_paths.get("error_review_queue", Path()).is_file():
        queue = load_predictions(output_paths["error_review_queue"])
        if len(queue) != output_entries["error_review_queue"].get("row_count"):
            errors.append("Queue row count mismatch")
        if len(queue) != len({row.get("record_id") for row in queue}):
            errors.append("Queue contains duplicate record_id")
        if len(queue) != len({row.get("split_group_id") for row in queue}):
            errors.append("Queue contains duplicate split_group_id")
        if any(row.get("source_label") == row.get("predicted_label") for row in queue):
            errors.append("Queue contains a correct prediction")
        if any("new_label" in row for row in queue):
            errors.append("Queue creates a new label")

    findings = registry.get("findings", {})
    if report:
        if findings.get("test_rows") != report.get("counts", {}).get("test_rows"):
            errors.append("Registry/report test row count mismatch")
        if findings.get("error_rows") != report.get("counts", {}).get("error_rows"):
            errors.append("Registry/report error row count mismatch")
        if findings.get("twitter_error_rows") != report.get("error_concentration", {}).get(
            "twitter_bot_detection_error_count"
        ):
            errors.append("Registry/report Twitter error count mismatch")
        if findings.get("review_queue_rows") != len(queue):
            errors.append("Registry/report queue count mismatch")

    reproduced_hashes = {}
    if not errors:
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            reproduced = analyze_frozen_errors(
                input_paths["group_split_dataset"],
                input_paths["model"],
                input_paths["test_predictions"],
                input_paths["results"],
                Path(temp_dir),
                run_at=report["run_at"],
            )
            if reproduced["counts"] != report["counts"]:
                errors.append("Reproduced count summary mismatch")
            for role, file_name in (
                ("error_analysis_report", "text_baseline_v2_error_analysis.json"),
                ("error_review_queue", "text_baseline_v2_error_review_queue.jsonl"),
            ):
                reproduced_hashes[role] = sha256_file(Path(temp_dir) / file_name)
                if reproduced_hashes[role] != output_entries[role]["sha256"]:
                    errors.append(f"Bit-for-bit reproduction mismatch: {role}")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "test_rows": report.get("counts", {}).get("test_rows") if report else None,
        "error_rows": report.get("counts", {}).get("error_rows") if report else None,
        "queue_rows": len(queue),
        "reproduced_sha256": reproduced_hashes,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
