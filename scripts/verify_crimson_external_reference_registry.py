"""Verify the frozen Crimson external-reference analysis registry and artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    errors: list[str] = []
    artifact_results: list[dict[str, object]] = []

    for role, item in registry.get("inputs", {}).items():
        path = Path(str(item.get("path", "")))
        if not path.is_file():
            errors.append(f"missing input {role}: {path}")
            continue
        actual = sha256_file(path)
        artifact_results.append({
            "role": f"input_{role}", "path": str(path),
            "expected_sha256": item.get("sha256"), "actual_sha256": actual,
            "status": "MATCH" if actual == item.get("sha256") else "MISMATCH",
        })
        if actual != item.get("sha256"):
            errors.append(f"input SHA-256 mismatch: {role}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"analysis_report", "reference_matches", "review_queue"}:
        errors.append("unexpected output roles")
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        if not path.is_file():
            errors.append(f"missing output {role}: {path}")
            continue
        actual = sha256_file(path)
        artifact_results.append({
            "role": role, "path": str(path),
            "expected_sha256": item.get("sha256"), "actual_sha256": actual,
            "status": "MATCH" if actual == item.get("sha256") else "MISMATCH",
        })
        if actual != item.get("sha256"):
            errors.append(f"output SHA-256 mismatch: {role}")
        if role != "analysis_report":
            with path.open(encoding="utf-8") as handle:
                count = sum(1 for line in handle if line.strip())
            if count != item.get("record_count"):
                errors.append(f"output record count mismatch: {role}")

    report_info = outputs.get("analysis_report", {})
    report_path = Path(str(report_info.get("path", "")))
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_coverage = report.get("coverage", {})
        registry_coverage = registry.get("coverage", {})
        for key in (
            "crimson_record_count", "unique_crimson_match_host_count",
            "crimson_records_with_reference_match", "crimson_records_without_reference_match",
            "unique_crimson_match_hosts_with_reference_match",
            "unique_crimson_match_hosts_without_reference_match",
            "reference_match_pair_count", "ambiguous_match_pair_count",
            "pair_counts_by_source", "pair_counts_by_host_relation", "queue_counts_by_reason",
        ):
            if report_coverage.get(key) != registry_coverage.get(key):
                errors.append(f"report/registry coverage mismatch: {key}")
        if report.get("outputs", {}).get("reference_matches", {}).get("sha256") != outputs.get(
            "reference_matches", {}
        ).get("sha256"):
            errors.append("report/registry reference-match hash mismatch")
        if report.get("outputs", {}).get("review_queue", {}).get("sha256") != outputs.get(
            "review_queue", {}
        ).get("sha256"):
            errors.append("report/registry review-queue hash mismatch")

    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("safety counts must remain zero")
    if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
        errors.append("training/domain-access gates must remain closed")
    if safety.get("automatic_entity_resolution_allowed") is not False:
        errors.append("automatic identity resolution must remain blocked")
    if safety.get("unmatched_means_safe") is not False:
        errors.append("unmatched domains cannot be marked safe")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
