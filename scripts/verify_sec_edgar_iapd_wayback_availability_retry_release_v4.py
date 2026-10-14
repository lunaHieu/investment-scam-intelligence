"""Independently verify the frozen SEC/IAPD Wayback retry V4 release."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v1 import read_jsonl
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Cooldown timestamp is timezone-naive")
    return parsed


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V4":
        errors.append("Unexpected V4 retry release identity")
    root = release_path.resolve().parents[1]
    for item in release.get("basis", []):
        if sha256_file(root / item["path"]) != item["sha256"]:
            errors.append(f"Basis hash mismatch: {item['path']}")
    for role, item in release.get("inputs", {}).items():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            errors.append(f"Input hash mismatch: {role}")
    prior = load_object(Path(release["inputs"]["partial_report_v3"]["path"]))
    qa = load_object(Path(release["inputs"]["independent_qa_v3"]["path"]))
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    if qa.get("status") != release["inputs"]["independent_qa_v3"]["required_status"]:
        errors.append("V3 independent QA status changed")
    if [row["availability_plan_id"] for row in plan] != [row["availability_plan_id"] for row in prior["results"]]:
        errors.append("Plan/V3 membership or order changed")
    resolved = sum(row.get("error") is None for row in prior["results"])
    unresolved = sum(row.get("error") is not None for row in prior["results"])
    observed = {
        "requested_candidate_count": len(prior["results"]),
        "cumulative_network_request_count": prior["cumulative_network_request_count"],
        "resolved_result_count": resolved,
        "available_snapshot_count": sum(row.get("available") is True for row in prior["results"]),
        "unavailable_snapshot_count": sum(row.get("available") is False for row in prior["results"]),
        "unresolved_error_count": unresolved,
        "stopped_on_http_429": prior["stopped_on_http_429"],
    }
    expected = release["prior_outcome_contract"]
    for key, value in observed.items():
        if expected.get(key) != value:
            errors.append(f"Prior outcome mismatch: {key}")
    cooldown = release["cooldown_contract"]
    cooldown_seconds = (parse_time(cooldown["not_before"]) - parse_time(cooldown["prior_attempt_created_at"])).total_seconds()
    if cooldown_seconds < 86400 or cooldown["minimum_cooldown_seconds"] != 86400:
        errors.append("V4 cooldown is not a full 24 hours")
    contract = release["retry_contract"]
    if contract["maximum_retry_candidate_count"] != unresolved or float(contract["minimum_delay_seconds"]) < 30.0:
        errors.append("V4 retry population or pacing changed")
    if contract["endpoint"] != "https://archive.org/wayback/available" or set(contract["allowed_network_hosts"]) != {"archive.org", "web.archive.org"}:
        errors.append("V4 endpoint or allowlist changed")
    if release["decision"].get("network_execution_allowed_now") is not False:
        errors.append("Release preparation unexpectedly authorizes immediate execution")
    closed_gates = ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed")
    for gate in closed_gates:
        if release["decision"].get(gate) is not False:
            errors.append(f"Forbidden gate opened: {gate}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_INDEPENDENT_QA_V4",
        "status": "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY" if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "partial_report_v3_sha256": sha256_file(Path(release["inputs"]["partial_report_v3"]["path"])), "independent_qa_v3_sha256": sha256_file(Path(release["inputs"]["independent_qa_v3"]["path"]))},
        "checks": {"plan_rows": len(plan), "resolved_rows_preserved": resolved, "retry_rows": unresolved, "minimum_cooldown_seconds": cooldown_seconds, "minimum_delay_seconds": contract["minimum_delay_seconds"], "network_execution_allowed_at_release_time": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.release)
    if args.output:
        if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
            raise FileExistsError("Refusing to overwrite V4 release QA")
        temporary = args.output.with_suffix(args.output.suffix + ".partial")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
