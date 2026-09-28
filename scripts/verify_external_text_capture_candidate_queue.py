"""Verify the frozen external-text capture candidate queue and safety state."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from validate_external_text_intake import sha256_file


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    registry = load_json(args.registry)
    errors: list[str] = []
    if registry.get("pilot_id") != "EXTERNAL_TEXT_CAPTURE_CANDIDATE_QUEUE_V1":
        errors.append("Unexpected pilot ID")
    if registry.get("status") != "FROZEN_CANDIDATE_QUEUE_CAPTURE_REQUIRED_NOT_LABELED":
        errors.append("Unexpected queue status")

    repository_root = args.registry.resolve().parents[2]
    for item in registry.get("inputs", []):
        registry_path = repository_root / str(item.get("registry"))
        if not registry_path.is_file():
            errors.append(f"Missing input registry: {registry_path}")
            continue
        input_registry = load_json(registry_path)
        matching_outputs = [
            output
            for output in input_registry.get("outputs", [])
            if output.get("role") == "reference_index"
        ]
        if len(matching_outputs) != 1:
            errors.append(f"Input registry has no unique reference index: {registry_path}")
            continue
        frozen = matching_outputs[0]
        if frozen.get("path") != item.get("path") or frozen.get("sha256") != item.get("sha256"):
            errors.append(f"Input registry metadata mismatch: {registry_path}")
        path = Path(str(item.get("path")))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Input artifact missing or changed: {path}")

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"capture_candidate_queue", "selection_report"}:
        errors.append("Output roles do not match queue contract")
    artifact_results = []
    for role, item in outputs.items():
        path = Path(str(item.get("path")))
        actual_hash = sha256_file(path) if path.is_file() else None
        artifact_results.append(
            {"role": role, "path": str(path), "expected_sha256": item.get("sha256"), "actual_sha256": actual_hash}
        )
        if actual_hash != item.get("sha256"):
            errors.append(f"Output artifact missing or changed: {role}")

    queue_path = Path(str(outputs.get("capture_candidate_queue", {}).get("path", "")))
    queue = load_jsonl(queue_path) if queue_path.is_file() else []
    target_counts = Counter(str(item.get("target_outcome")) for item in queue)
    if target_counts != Counter({"CONFIRMED_CANDIDATE": 15, "LEGITIMATE_CANDIDATE": 15}):
        errors.append("Queue is not balanced at 15 plus 15")
    candidate_ids = [item.get("candidate_id") for item in queue]
    candidate_hosts = [item.get("candidate_host") for item in queue]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("Candidate IDs are not unique")
    if len(candidate_hosts) != len(set(candidate_hosts)):
        errors.append("Candidate hosts are not unique")
    for item in queue:
        review = item.get("review_state", {})
        if review.get("ground_truth_status") != "UNCERTAIN":
            errors.append(f"Candidate was promoted to a label: {item.get('candidate_id')}")
        if review.get("label_confidence") != "LOW" or review.get("review_status") != "UNREVIEWED":
            errors.append(f"Candidate review state is not frozen: {item.get('candidate_id')}")
        if item.get("label_created") is not False or item.get("training_eligible") != "NO":
            errors.append(f"Candidate is labeled or training eligible: {item.get('candidate_id')}")

    report_path = Path(str(outputs.get("selection_report", {}).get("path", "")))
    report = load_json(report_path) if report_path.is_file() else {}
    if report.get("selected_counts") != {
        "CONFIRMED_CANDIDATE": 15,
        "LEGITIMATE_CANDIDATE": 15,
        "total": 30,
    }:
        errors.append("Selection report counts do not match the frozen protocol")
    report_safety = report.get("safety_contract", {})
    registry_safety = registry.get("safety_contract", {})
    for safety in (report_safety, registry_safety):
        if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
            errors.append("Queue creation must remain offline and unlabeled")
        if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
            errors.append("Training and domain-access gates must remain closed")

    result = {
        "pilot_id": registry.get("pilot_id"),
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(queue),
        "target_counts": dict(sorted(target_counts.items())),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
