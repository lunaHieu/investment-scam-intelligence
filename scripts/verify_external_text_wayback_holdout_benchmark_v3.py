"""Verify the hash-pinned Wayback holdout V3 benchmark and all frozen gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_external_text_wayback_language_benchmark_v2 import (
    validate_benchmark,
    validate_primary_packet_raw,
)
from src.isi.normalization.external_references import sha256_file


REQUIRED_ROLES = {
    "protocol_config",
    "candidate_queue",
    "availability_report",
    "capture_plan",
    "capture_report",
    "capture_audit",
    "balanced_usable_capture_view",
    "offline_screening",
    "primary_review_packet",
    "primary_review_policy",
    "primary_review",
    "blind_second_review_preparation_report",
    "blind_second_review_packet",
    "private_second_review_mapping",
    "independent_second_review_response",
    "independent_second_review",
    "reconciliation_report",
    "benchmark",
}


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    if registry.get("registry_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_BENCHMARK_V3":
        raise ValueError("Unexpected V3 registry ID")
    roles: dict[str, Path] = {}
    for artifact in registry["artifacts"]:
        path = resolve_path(str(artifact["path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        if sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"Artifact SHA-256 mismatch: {path}")
        role = str(artifact["role"])
        if role in roles:
            raise ValueError(f"Duplicate artifact role: {role}")
        roles[role] = path
    missing_roles = REQUIRED_ROLES - set(roles)
    if missing_roles:
        raise ValueError(f"Missing required artifact roles: {sorted(missing_roles)}")
    benchmark = json.loads(roles["benchmark"].read_text(encoding="utf-8"))
    if benchmark.get("benchmark_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_BENCHMARK_V3":
        raise ValueError("Unexpected V3 benchmark ID")
    counts = validate_benchmark(benchmark, int(registry["counts"]["benchmark_records"]))
    primary_packet = json.loads(roles["primary_review_packet"].read_text(encoding="utf-8"))
    verified_raw_capture_count = validate_primary_packet_raw(primary_packet)
    if verified_raw_capture_count != registry["counts"]["primary_reviewed"]:
        raise ValueError("Primary packet raw-capture count does not match registry")
    report = json.loads(roles["reconciliation_report"].read_text(encoding="utf-8"))
    if report["counts"]["materialized_records"] != registry["counts"]["benchmark_records"]:
        raise ValueError("Reconciliation count does not match registry")
    if report["counts"]["matched_per_class"] < registry["gates"]["english_minimum_per_class"]:
        raise ValueError("English minimum is not met")
    if report["gates"]["owner_acceptance_complete"] is not False or report["gates"]["model_scoring_allowed"] is not False:
        raise ValueError("Reconciliation report incorrectly opens scoring")
    second = json.loads(roles["independent_second_review"].read_text(encoding="utf-8"))
    if second["safety_contract"]["mapping_exposed_to_reviewer"] is not False:
        raise ValueError("Second review was not blind to mapping")
    if second["safety_contract"]["independent_human_review_claimed"] is not False:
        raise ValueError("Second review incorrectly claims to be human")
    screening_lines = sum(1 for line in roles["offline_screening"].read_text(encoding="utf-8").splitlines() if line.strip())
    if screening_lines != registry["counts"]["screened_usable_captures"]:
        raise ValueError("Offline-screening count does not match registry")
    print(json.dumps({
        "status": "OK",
        "registry": str(args.registry),
        "verified_artifact_count": len(registry["artifacts"]),
        "verified_raw_capture_count": verified_raw_capture_count,
        "verified_screening_count": screening_lines,
        "benchmark_counts": counts,
        "owner_acceptance_complete": False,
        "model_scoring_allowed": False,
        "training_allowed": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
