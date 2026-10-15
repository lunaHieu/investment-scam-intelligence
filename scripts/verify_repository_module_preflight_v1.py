"""Verify the immutable active-module preflight report offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PROTOCOL_ID = "ISI_REPOSITORY_MODULE_PREFLIGHT_V1"
EXPECTED_REPORT_ID = "ISI_REPOSITORY_MODULE_PREFLIGHT_REPORT_V1"


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


def verify(config_path: Path, report_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    report = load_object(report_path)
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        raise ValueError("Unexpected module-preflight protocol ID")
    if report.get("report_id") != EXPECTED_REPORT_ID:
        raise ValueError("Unexpected module-preflight report ID")
    if report.get("status") != "PASS_ALL_ACTIVE_MODULES_IMPORTABLE":
        raise ValueError("Module preflight did not pass")
    if report.get("protocol", {}).get("sha256") != sha256_file(config_path):
        raise ValueError("Report is not bound to the current protocol")
    frozen_at = datetime.fromisoformat(str(config["frozen_at"]))
    created_at = datetime.fromisoformat(str(report["created_at"]))
    if frozen_at.tzinfo is None or created_at.tzinfo is None:
        raise ValueError("Protocol and report times must be timezone-aware")
    if created_at.astimezone(timezone.utc) < frozen_at.astimezone(timezone.utc):
        raise ValueError("Report predates the frozen protocol")

    root = config_path.resolve().parents[1]
    expected = {item["module"]: item for item in config["modules"]}
    results = report.get("results")
    if not isinstance(results, list):
        raise ValueError("Report results must be a list")
    actual = {item.get("module"): item for item in results if isinstance(item, dict)}
    if set(actual) != set(expected) or len(actual) != len(results):
        raise ValueError("Report module population does not match protocol")
    for module, item in expected.items():
        result = actual[module]
        source = root / item["path"]
        source_hash = sha256_file(source) if source.is_file() else None
        if source_hash != item["sha256"] or result.get("source_sha256") != source_hash:
            raise ValueError(f"Source missing or changed: {module}")
        if result.get("status") != "PASS_IMPORTABLE" or result.get("returncode") != 0:
            raise ValueError(f"Module was not importable: {module}")
    if report.get("module_count") != len(expected) or report.get("passed_count") != len(expected):
        raise ValueError("Report counts do not match module population")
    if report.get("failed_count") != 0:
        raise ValueError("Report contains failed modules")
    safety = report.get("safety_contract", {})
    if any(value != 0 for value in safety.values()):
        raise ValueError("Preflight safety contract records an operation")
    return {
        "valid": True,
        "module_count": len(expected),
        "passed_count": len(expected),
        "network_operations": safety.get("network_operations"),
        "main_functions_invoked": safety.get("main_functions_invoked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.config, args.report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
