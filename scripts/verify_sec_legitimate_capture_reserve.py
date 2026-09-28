"""Verify the frozen offline SEC legitimate reserve queue and closed gates."""

from __future__ import annotations

import argparse
import json
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
    root = args.registry.resolve().parents[2]
    errors: list[str] = []
    artifact_results: list[dict] = []

    if registry.get("pilot_id") != "SEC_LEGITIMATE_CAPTURE_RESERVE_V1":
        errors.append("Unexpected pilot ID")
    if registry.get("status") != "FROZEN_OFFLINE_RESERVE_QUEUE_CAPTURE_REQUIRED_NOT_LABELED":
        errors.append("Unexpected reserve status")

    primary_hosts: set[str] = set()
    for item in registry.get("inputs", []):
        input_registry_path = root / str(item.get("registry", ""))
        if not input_registry_path.is_file():
            errors.append(f"Missing input registry: {input_registry_path}")
            continue
        input_registry = load_json(input_registry_path)
        expected_role = "capture_candidate_queue" if item.get("role") == "primary_capture_queue" else "reference_index"
        matches = [output for output in input_registry.get("outputs", []) if output.get("role") == expected_role]
        if len(matches) != 1:
            errors.append(f"Input registry has no unique {expected_role}: {input_registry_path}")
            continue
        frozen = matches[0]
        if frozen.get("path") != item.get("path") or frozen.get("sha256") != item.get("sha256"):
            errors.append(f"Input metadata mismatch: {input_registry_path}")
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            errors.append(f"Input artifact missing or changed: {path}")
        if item.get("role") == "primary_capture_queue" and path.is_file():
            primary_hosts = {
                str(record.get("candidate_host", "")).casefold().rstrip(".")
                for record in load_jsonl(path)
            }

    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    if set(outputs) != {"sec_legitimate_reserve_queue", "selection_report"}:
        errors.append("Output roles do not match the reserve contract")
    for role, item in outputs.items():
        path = Path(str(item.get("path", "")))
        actual = sha256_file(path) if path.is_file() else None
        artifact_results.append(
            {"role": role, "path": str(path), "expected_sha256": item.get("sha256"), "actual_sha256": actual}
        )
        if actual != item.get("sha256"):
            errors.append(f"Output artifact missing or changed: {role}")

    queue_path = Path(str(outputs.get("sec_legitimate_reserve_queue", {}).get("path", "")))
    queue = load_jsonl(queue_path) if queue_path.is_file() else []
    if len(queue) != 30:
        errors.append("Reserve queue must contain exactly 30 records")
    ids = [item.get("candidate_id") for item in queue]
    hosts = [str(item.get("candidate_host", "")).casefold().rstrip(".") for item in queue]
    if len(ids) != len(set(ids)) or len(hosts) != len(set(hosts)):
        errors.append("Reserve candidate IDs and hosts must be unique")
    if primary_hosts.intersection(hosts):
        errors.append("Reserve queue overlaps the primary queue")
    for item in queue:
        review = item.get("review_state", {})
        signals = item.get("selection_signals", {})
        if item.get("target_outcome") != "LEGITIMATE_RESERVE_CANDIDATE":
            errors.append(f"Unexpected target: {item.get('candidate_id')}")
        if review.get("ground_truth_status") != "UNCERTAIN":
            errors.append(f"Candidate was promoted to a label: {item.get('candidate_id')}")
        if review.get("label_confidence") != "LOW" or review.get("review_status") != "UNREVIEWED":
            errors.append(f"Candidate review state is not frozen: {item.get('candidate_id')}")
        if item.get("label_created") is not False or item.get("training_eligible") != "NO":
            errors.append(f"Candidate is labeled or training eligible: {item.get('candidate_id')}")
        if float(signals.get("domain_identity_affinity", 0.0)) < 0.45:
            errors.append(f"Candidate affinity is below threshold: {item.get('candidate_id')}")
        if signals.get("sec_host_unique") is not True or signals.get("iosco_collision") is not False:
            errors.append(f"Candidate collision signals are invalid: {item.get('candidate_id')}")

    report_path = Path(str(outputs.get("selection_report", {}).get("path", "")))
    report = load_json(report_path) if report_path.is_file() else {}
    if report.get("selected_count") != 30 or report.get("requested_reserve_size") != 30:
        errors.append("Selection report counts do not match the frozen protocol")
    if report.get("eligible_pool_count") != 2222:
        errors.append("Eligible pool count changed")
    for safety in (report.get("safety_contract", {}), registry.get("safety_contract", {})):
        if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
            errors.append("Reserve selection must remain offline and unlabeled")
        if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
            errors.append("Training and domain-access gates must remain closed")

    result = {
        "pilot_id": registry.get("pilot_id"),
        "status": "VALID" if not errors else "INVALID",
        "record_count": len(queue),
        "primary_overlap_count": len(primary_hosts.intersection(hosts)),
        "artifact_results": artifact_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
