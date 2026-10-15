"""Independently verify the frozen SEC/IAPD Wayback retry V5 release."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.retry_sec_edgar_iapd_wayback_availability_v4 import read_jsonl
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def verify(release_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_V5":
        errors.append("Unexpected V5 retry release identity")
    root = release_path.resolve().parents[1]
    for item in release.get("basis", []):
        if sha256_file(root / item["path"]) != item["sha256"]:
            errors.append(f"Basis hash mismatch: {item['path']}")
    for role, item in release.get("inputs", {}).items():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            errors.append(f"Input hash mismatch: {role}")
    prior = load_object(Path(release["inputs"]["partial_report_v4"]["path"]))
    qa = load_object(Path(release["inputs"]["independent_qa_v4"]["path"]))
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    if qa.get("status") != "PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED":
        errors.append("V4 independent QA status changed")
    if [row["availability_plan_id"] for row in plan] != [row["availability_plan_id"] for row in prior["results"]]:
        errors.append("Plan/V4 membership or order changed")
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
    for key, value in observed.items():
        if release["prior_outcome_contract"].get(key) != value:
            errors.append(f"Prior outcome mismatch: {key}")
    cooldown = release["cooldown_contract"]
    prior_at = datetime.fromisoformat(cooldown["prior_attempt_created_at"])
    not_before = datetime.fromisoformat(cooldown["not_before"])
    cooldown_seconds = (not_before - prior_at).total_seconds()
    if cooldown_seconds < 86400 or cooldown["minimum_cooldown_seconds"] != 86400:
        errors.append("V5 cooldown is not a full 24 hours")
    contract = release["retry_contract"]
    if contract["maximum_retry_candidate_count"] != unresolved or float(contract["minimum_delay_seconds"]) < 60.0:
        errors.append("V5 retry population or slower pacing changed")
    if contract["endpoint"] != "https://archive.org/wayback/available" or set(contract["allowed_network_hosts"]) != {"archive.org", "web.archive.org"}:
        errors.append("V5 endpoint or allowlist changed")
    if release["decision"].get("network_execution_allowed_now") is not False:
        errors.append("V5 preparation authorizes immediate execution")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if release["decision"].get(gate) is not False:
            errors.append(f"Forbidden gate opened: {gate}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RETRY_RELEASE_INDEPENDENT_QA_V5",
        "status": "PASS_FROZEN_NOT_BEFORE_24H_UNRESOLVED_ONLY_SLOWER_PACING" if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "partial_report_v4_sha256": sha256_file(Path(release["inputs"]["partial_report_v4"]["path"])), "independent_qa_v4_sha256": sha256_file(Path(release["inputs"]["independent_qa_v4"]["path"]))},
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
            raise FileExistsError("Refusing to overwrite V5 release QA")
        temporary = args.output.with_suffix(args.output.suffix + ".partial")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
