"""Verify the hash-pinned Wayback language benchmark V2 and its frozen gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def validate_benchmark(benchmark: dict[str, object], expected_count: int) -> dict[str, int]:
    if benchmark.get("status") != "OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING":
        raise ValueError("Benchmark scoring gate is not frozen")
    if benchmark.get("training_eligible") is not False:
        raise ValueError("Benchmark incorrectly allows training")
    contract = benchmark.get("model_input_contract", {})
    if contract.get("allowed_input") != "artifact.visible_text only":
        raise ValueError("Unexpected model-input contract")
    if contract.get("warning_or_registry_evidence_as_model_input_allowed") is not False:
        raise ValueError("Evidence leakage into model input is allowed")
    records = benchmark.get("records", [])
    if len(records) != expected_count:
        raise ValueError(f"Unexpected benchmark size: {len(records)} != {expected_count}")
    if len({row["benchmark_record_id"] for row in records}) != len(records):
        raise ValueError("Duplicate benchmark record ID")
    if len({row["review_provenance"]["source_candidate_id"] for row in records}) != len(records):
        raise ValueError("Duplicate source candidate ID")
    counts = Counter()
    for row in records:
        status = row.get("ground_truth_status")
        if status not in {"CONFIRMED", "LEGITIMATE"}:
            raise ValueError("Unsupported ground-truth status")
        counts[str(status)] += 1
        if row.get("language_stratum") != "ENGLISH":
            raise ValueError("Non-English record entered the English benchmark")
        if row.get("capture_stratum") != "WAYBACK_ARCHIVED_HOMEPAGE_HTML":
            raise ValueError("Capture stratum mismatch")
        if row.get("label_confidence") != "HIGH" or row.get("training_eligible") is not False:
            raise ValueError("Review confidence or training gate mismatch")
        text = str(row["artifact"]["visible_text"])
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != row["artifact"]["text_sha256"]:
            raise ValueError("Visible-text SHA-256 mismatch")
        provenance = row["review_provenance"]
        if provenance.get("primary_decision") != status or provenance.get("second_decision") != status:
            raise ValueError("Primary/second-review decision mismatch")
        if provenance.get("primary_confidence") != "HIGH" or provenance.get("second_confidence") != "HIGH":
            raise ValueError("Benchmark includes a non-HIGH agreement")
        if provenance.get("independent_human_second_review") is not False:
            raise ValueError("Benchmark incorrectly claims independent human review")
    if counts["CONFIRMED"] != counts["LEGITIMATE"]:
        raise ValueError("Benchmark classes are not balanced")
    return dict(counts)


def validate_primary_packet_raw(packet: dict[str, object]) -> int:
    verified = 0
    for item in packet.get("items", []):
        artifact = item["artifact"]
        path = Path(str(artifact["capture_path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        if sha256_file(path) != artifact["capture_sha256"]:
            raise ValueError(f"Raw capture SHA-256 mismatch: {path}")
        text = str(artifact["visible_text"])
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != artifact["text_sha256"]:
            raise ValueError(f"Primary-packet text SHA-256 mismatch: {item['candidate_id']}")
        verified += 1
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    roles: dict[str, Path] = {}
    for artifact in registry["artifacts"]:
        path = resolve_path(str(artifact["path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        if sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"Artifact SHA-256 mismatch: {path}")
        roles[str(artifact["role"])] = path
    benchmark = json.loads(roles["benchmark"].read_text(encoding="utf-8"))
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
    print(json.dumps({"status": "OK", "registry": str(args.registry), "verified_artifact_count": len(registry["artifacts"]), "verified_raw_capture_count": verified_raw_capture_count, "benchmark_counts": counts, "model_scoring_allowed": False, "training_allowed": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
