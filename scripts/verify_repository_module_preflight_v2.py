"""Independently verify the immutable SEC/IAPD V5 module-preflight report."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PROTOCOL_ID = "ISI_REPOSITORY_MODULE_PREFLIGHT_V2"
EXPECTED_REPORT_ID = "ISI_REPOSITORY_MODULE_PREFLIGHT_REPORT_V2"
EXPECTED_MODULES = {
    "scripts.retry_sec_edgar_iapd_wayback_availability_v5",
    "scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v5",
    "scripts.verify_sec_edgar_iapd_wayback_availability_result_v5",
}


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
    if report.get("status") != "PASS_ALL_V5_MODULES_IMPORTABLE":
        raise ValueError("V5 module preflight did not pass")
    if report.get("protocol", {}).get("sha256") != sha256_file(config_path):
        raise ValueError("Report is not bound to the current protocol")
    frozen_at = datetime.fromisoformat(str(config["frozen_at"]))
    created_at = datetime.fromisoformat(str(report["created_at"]))
    if frozen_at.tzinfo is None or created_at.tzinfo is None:
        raise ValueError("Protocol and report times must be timezone-aware")
    if created_at.astimezone(timezone.utc) < frozen_at.astimezone(timezone.utc):
        raise ValueError("Report predates the frozen protocol")

    contract = config.get("execution_contract", {})
    if contract.get("invoke_main_allowed") is not False:
        raise ValueError("Protocol permits main invocation")
    if contract.get("network_allowed") is not False:
        raise ValueError("Protocol permits network access")
    if contract.get("write_bytecode_allowed") is not False:
        raise ValueError("Protocol permits bytecode writes")
    if contract.get("output_overwrite_allowed") is not False:
        raise ValueError("Protocol permits report overwrite")

    root = config_path.resolve().parents[1]
    modules = config.get("modules")
    if not isinstance(modules, list) or len(modules) != 3:
        raise ValueError("V2 protocol must contain exactly three modules")
    expected = {item["module"]: item for item in modules}
    if set(expected) != EXPECTED_MODULES or len(expected) != len(modules):
        raise ValueError("Protocol module population is not the frozen V5 set")
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
    if report.get("module_count") != 3 or report.get("passed_count") != 3:
        raise ValueError("Report counts do not match the V5 module population")
    if report.get("failed_count") != 0:
        raise ValueError("Report contains failed modules")
    safety = report.get("safety_contract", {})
    if set(safety) != {
        "main_functions_invoked",
        "network_operations",
        "raw_file_modifications",
        "labels_created",
        "model_operations",
        "validation_or_test_openings",
    }:
        raise ValueError("Report safety contract fields are incomplete or unexpected")
    if any(value != 0 for value in safety.values()):
        raise ValueError("Preflight safety contract records an operation")
    return {
        "valid": True,
        "module_count": 3,
        "passed_count": 3,
        "network_operations": 0,
        "main_functions_invoked": 0,
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
