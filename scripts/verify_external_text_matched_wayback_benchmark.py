"""Verify the matched Wayback benchmark, reviews, provenance, and closed model gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PILOT_ID = "EXTERNAL_TEXT_MATCHED_WAYBACK_BENCHMARK_V1"
STRATUM = "WAYBACK_ARCHIVED_HOMEPAGE_HTML"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    checked = []
    if registry.get("pilot_id") != PILOT_ID:
        errors.append("Unexpected pilot ID")
    if registry.get("status") != "MATCHED_REVIEWED_BENCHMARK_OWNER_ACCEPTANCE_REQUIRED":
        errors.append("Unexpected registry status")

    entries = (
        list(registry.get("implementation", []))
        + list(registry.get("inputs", []))
        + list(registry.get("outputs", []))
    )
    for item in entries:
        path = resolve(root, item.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        checked.append({"role": item.get("role"), "path": str(path), "sha256": actual})
        if actual != item.get("sha256"):
            errors.append(f"Artifact missing or changed: {item.get('role')}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"benchmark", "reconciliation_report", "primary_second_review", "reserve_second_review"}:
        errors.append("Unexpected output roles")
    benchmark_path = resolve(root, outputs.get("benchmark", {}).get("path", ""))
    report_path = resolve(root, outputs.get("reconciliation_report", {}).get("path", ""))
    benchmark = load_json(benchmark_path) if benchmark_path.is_file() else {}
    report = load_json(report_path) if report_path.is_file() else {}
    records = benchmark.get("records", [])
    if benchmark.get("benchmark_id") != PILOT_ID:
        errors.append("Benchmark ID mismatch")
    if benchmark.get("status") != "OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING":
        errors.append("Benchmark model-scoring gate is unexpectedly open")
    ids = [item.get("benchmark_record_id") for item in records]
    if len(records) != 18 or len(set(ids)) != 18:
        errors.append("Expected 18 unique benchmark records")
    class_counts = {
        status: sum(item.get("ground_truth_status") == status for item in records)
        for status in ("CONFIRMED", "LEGITIMATE")
    }
    if class_counts != {"CONFIRMED": 9, "LEGITIMATE": 9}:
        errors.append(f"Unexpected benchmark class counts: {class_counts}")
    if {item.get("capture_stratum") for item in records} != {STRATUM}:
        errors.append("Benchmark contains an unmatched capture stratum")
    text_hashes = set()
    capture_hashes = set()
    for item in records:
        artifact = item.get("artifact", {})
        text_hash = hashlib.sha256(str(artifact.get("text", "")).encode("utf-8")).hexdigest()
        if text_hash != artifact.get("text_sha256"):
            errors.append(f"Text hash mismatch: {item.get('benchmark_record_id')}")
        capture_path = Path(str(artifact.get("source_capture_path", "")))
        if not capture_path.is_file() or sha256_file(capture_path) != artifact.get("source_capture_sha256"):
            errors.append(f"Capture missing or changed: {item.get('benchmark_record_id')}")
        text_hashes.add(text_hash)
        capture_hashes.add(artifact.get("source_capture_sha256"))
        provenance = item.get("review_provenance", {})
        if (
            provenance.get("independent_ai_second_review") is not True
            or provenance.get("independent_human_second_review") is not False
            or provenance.get("second_review_decision") != item.get("ground_truth_status")
            or provenance.get("second_review_confidence") != "HIGH"
        ):
            errors.append(f"Review provenance mismatch: {item.get('benchmark_record_id')}")
        if item.get("training_eligible") is not False:
            errors.append(f"Training gate open: {item.get('benchmark_record_id')}")
    if len(text_hashes) != 18 or len(capture_hashes) != 18:
        errors.append("Benchmark contains duplicate text or capture hashes")

    expected_counts = {
        "confirmed_agreements": 9,
        "legitimate_agreements": 11,
        "matched_per_class": 9,
        "materialized_records": 18,
    }
    if report.get("counts") != expected_counts:
        errors.append("Unexpected reconciliation counts")
    if len(report.get("nonagreements", [])) != 5:
        errors.append("Expected five preserved nonagreements")
    gates = report.get("gates", {})
    if (
        gates.get("capture_stratum_contains_both_classes") is not True
        or gates.get("class_counts_balanced") is not True
        or gates.get("second_review_complete") is not True
        or gates.get("owner_acceptance_complete") is not False
        or gates.get("model_scoring_allowed") is not False
        or gates.get("training_allowed") is not False
        or gates.get("deployment_allowed") is not False
    ):
        errors.append("Reconciliation gates do not match the frozen protocol")
    safety = registry.get("safety_contract", {})
    for key, expected in {
        "model_scoring_operations": 0,
        "model_fit_operations": 0,
        "independent_human_review_claimed": False,
        "training_allowed": False,
        "deployment_allowed": False,
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Registry safety contract mismatch: {key}")

    serialized = json.dumps(benchmark, ensure_ascii=False)
    for prohibited in ("score_label_1", "predicted_source_label", "model_prediction"):
        if prohibited in serialized:
            errors.append(f"Benchmark leaks prohibited model output: {prohibited}")
    result = {
        "pilot_id": registry.get("pilot_id"),
        "valid": not errors,
        "record_count": len(records),
        "class_counts": class_counts,
        "capture_strata": sorted({item.get("capture_stratum") for item in records}),
        "checked": checked,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
