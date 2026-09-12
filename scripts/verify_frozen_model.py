"""Verify frozen model registry invariants and artifact SHA-256 values."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path


def file_sha256(path: Path) -> str:
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

    if registry.get("status") != "FROZEN_INTERNAL_BASELINE_NOT_FOR_DEPLOYMENT":
        errors.append("registry status is not the expected frozen internal status")
    data_contract = registry.get("data_contract", {})
    if data_contract.get("surface_normalized_cross_split_groups") != 0:
        errors.append("surface-normalized cross-split groups must be zero")
    if data_contract.get("template_candidate_cross_split_groups") != 0:
        errors.append("template-candidate cross-split groups must be zero")
    if registry.get("selection_policy", {}).get("test_used_for_selection") is not False:
        errors.append("test_used_for_selection must be false")

    artifact_results = []
    roles = set()
    for artifact in registry.get("artifacts", []):
        role = artifact.get("role")
        path = Path(artifact.get("path", ""))
        expected = str(artifact.get("sha256", "")).lower()
        if role in roles:
            errors.append(f"duplicate artifact role: {role}")
        roles.add(role)
        if not path.is_file():
            errors.append(f"missing artifact: {path}")
            artifact_results.append({"role": role, "path": str(path), "status": "MISSING"})
            continue
        actual = file_sha256(path)
        status = "MATCH" if actual == expected else "MISMATCH"
        artifact_results.append({
            "role": role,
            "path": str(path),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "status": status,
        })
        if status != "MATCH":
            errors.append(f"SHA-256 mismatch: {path}")

    expected_roles = {
        "group_split_dataset", "model", "primary_results", "cross_source_results",
        "model_comparison", "paired_error_comparison",
    }
    missing_roles = expected_roles - roles
    if missing_roles:
        errors.append(f"missing artifact roles: {sorted(missing_roles)}")

    runtime = registry.get("runtime", {})
    installed = {
        "python": ".".join(map(str, sys.version_info[:3])),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "joblib": importlib.metadata.version("joblib"),
    }
    runtime_matches = {name: installed[name] == expected for name, expected in runtime.items()}
    for name, matches in runtime_matches.items():
        if not matches:
            errors.append(f"runtime version mismatch for {name}: expected {runtime[name]}, got {installed[name]}")

    result = {
        "registry": str(args.registry),
        "model_id": registry.get("model_id"),
        "artifact_results": artifact_results,
        "runtime_installed": installed,
        "runtime_matches": runtime_matches,
        "status": "VALID" if not errors else "INVALID",
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
