"""Verify frozen Crimson unsupervised analysis registry and artifact hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    errors = []
    results = []

    input_info = registry.get("input", {})
    input_path = Path(input_info.get("path", ""))
    if not input_path.is_file():
        errors.append(f"missing input feature set: {input_path}")
    else:
        actual = sha256_file(input_path)
        results.append({"role": "input", "path": str(input_path), "actual_sha256": actual})
        if actual != input_info.get("sha256"):
            errors.append("input feature-set SHA-256 mismatch")

    output_by_role = {}
    for output in registry.get("outputs", []):
        role = output.get("role")
        path = Path(output.get("path", ""))
        expected = output.get("sha256")
        if role in output_by_role:
            errors.append(f"duplicate output role: {role}")
            continue
        output_by_role[role] = path
        if not path.is_file():
            errors.append(f"missing output: {path}")
            continue
        actual = sha256_file(path)
        results.append({
            "role": role, "path": str(path), "expected_sha256": expected,
            "actual_sha256": actual, "status": "MATCH" if actual == expected else "MISMATCH",
        })
        if actual != expected:
            errors.append(f"SHA-256 mismatch: {path}")

    required_roles = {"analysis_report", "domain_assignments", "review_queue"}
    if set(output_by_role) != required_roles:
        errors.append(f"output roles must be exactly {sorted(required_roles)}")
    report_path = output_by_role.get("analysis_report")
    if report_path and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        checks = {
            "record_count": report.get("record_count") == input_info.get("record_count"),
            "selected_cluster_count": report.get("cluster_selection", {}).get("selected_cluster_count")
            == registry.get("method", {}).get("selected_cluster_count"),
            "mean_ari": report.get("stability", {}).get("mean_adjusted_rand_index")
            == registry.get("quality", {}).get("mean_adjusted_rand_index_across_seeds"),
            "network_operations": report.get("network_operations") == 0,
            "labels_created": report.get("labels_created") == 0,
            "training_allowed": report.get("training_allowed") is False,
            "queue_count": report.get("review_queue", {}).get("record_count")
            == registry.get("review_queue", {}).get("record_count"),
        }
        for name, passed in checks.items():
            if not passed:
                errors.append(f"report/registry invariant failed: {name}")

    safety = registry.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("registry safety counts must be zero")
    if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
        errors.append("registry safety gates must remain false")

    result = {
        "analysis_id": registry.get("analysis_id"),
        "status": "VALID" if not errors else "INVALID",
        "artifact_results": results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
