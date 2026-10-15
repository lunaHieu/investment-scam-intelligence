"""Import active repository entrypoints in isolated offline subprocesses."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PROTOCOL_ID = "ISI_REPOSITORY_MODULE_PREFLIGHT_V1"
EXPECTED_REPORT_ID = "ISI_REPOSITORY_MODULE_PREFLIGHT_REPORT_V1"
IMPORT_CODE = "import importlib,sys; importlib.import_module(sys.argv[1])"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def run_preflight(config_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        raise ValueError("Unexpected module-preflight protocol ID")
    frozen_at = datetime.fromisoformat(str(config["frozen_at"]))
    if frozen_at.tzinfo is None:
        raise ValueError("Protocol frozen_at must be timezone-aware")
    if datetime.now(timezone.utc) < frozen_at.astimezone(timezone.utc):
        raise ValueError("Protocol is not frozen yet")
    contract = config["execution_contract"]
    if contract["invoke_main_allowed"] is not False or contract["network_allowed"] is not False:
        raise ValueError("Preflight would invoke main or allow network")
    if contract["write_bytecode_allowed"] is not False:
        raise ValueError("Preflight bytecode-write gate was opened")
    if contract["output_overwrite_allowed"] is not False:
        raise ValueError("Preflight output overwrite gate was opened")

    root = Path(config["repository_root"]).resolve()
    if root != config_path.resolve().parents[1]:
        raise ValueError("Configured repository root does not match config location")
    target = output_path or Path(config["planned_output"]["path"])
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite preflight report: {target}")

    timeout = int(contract["import_timeout_seconds_per_module"])
    if timeout < 1 or timeout > 60:
        raise ValueError("Import timeout must remain within 1-60 seconds")
    modules = config.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("No modules declared")

    seen_modules: set[str] = set()
    seen_paths: set[str] = set()
    results: list[dict[str, Any]] = []
    child_env = os.environ.copy()
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    for item in modules:
        module = str(item["module"])
        relative = str(item["path"])
        if module in seen_modules or relative in seen_paths:
            raise ValueError("Duplicate module or source path")
        seen_modules.add(module)
        seen_paths.add(relative)
        source_path = root / relative
        actual_hash = sha256_file(source_path) if source_path.is_file() else None
        if actual_hash != item["sha256"]:
            results.append(
                {
                    "role": item["role"],
                    "module": module,
                    "path": relative,
                    "source_sha256": actual_hash,
                    "status": "FAIL_SOURCE_MISSING_OR_HASH_CHANGED",
                    "returncode": None,
                    "stdout_bytes": 0,
                    "stderr_bytes": 0
                }
            )
            continue
        try:
            process = subprocess.run(
                [sys.executable, "-c", IMPORT_CODE, module],
                cwd=root,
                env=child_env,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            status = "PASS_IMPORTABLE" if process.returncode == 0 else "FAIL_IMPORT_ERROR"
            results.append(
                {
                    "role": item["role"],
                    "module": module,
                    "path": relative,
                    "source_sha256": actual_hash,
                    "status": status,
                    "returncode": process.returncode,
                    "stdout_bytes": len(process.stdout),
                    "stderr_bytes": len(process.stderr),
                    "stderr_sha256": hashlib.sha256(process.stderr).hexdigest()
                    if process.stderr
                    else None,
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "role": item["role"],
                    "module": module,
                    "path": relative,
                    "source_sha256": actual_hash,
                    "status": "FAIL_IMPORT_TIMEOUT",
                    "returncode": None,
                    "stdout_bytes": 0,
                    "stderr_bytes": 0,
                }
            )

    all_passed = all(item["status"] == "PASS_IMPORTABLE" for item in results)
    report = {
        "report_id": EXPECTED_REPORT_ID,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "PASS_ALL_ACTIVE_MODULES_IMPORTABLE" if all_passed else "FAIL_MODULE_IMPORTS",
        "protocol": {
            "path": str(config_path.resolve()),
            "sha256": sha256_file(config_path),
        },
        "python_executable": str(Path(sys.executable).resolve()),
        "repository_root": str(root),
        "module_count": len(results),
        "passed_count": sum(item["status"] == "PASS_IMPORTABLE" for item in results),
        "failed_count": sum(item["status"] != "PASS_IMPORTABLE" for item in results),
        "results": results,
        "safety_contract": {
            "main_functions_invoked": 0,
            "network_operations": 0,
            "raw_file_modifications": 0,
            "labels_created": 0,
            "model_operations": 0,
            "validation_or_test_openings": 0,
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_preflight(args.config, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
