"""Independently verify the first SEC/IAPD Wayback availability result."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def valid_snapshot_url(value: str, timestamp: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme == "https" and parsed.hostname == "web.archive.org" and bool(re.match(r"^/web/\d{14}/https?://", parsed.path)) and bool(re.fullmatch(r"\d{14}", timestamp))


def verify(release_path: Path, result_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    report = load_object(result_path)
    plan_path = Path(release["inputs"]["availability_plan"]["path"])
    plan = read_jsonl(plan_path)
    errors: list[str] = []
    if report.get("report_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_REPORT_V1":
        errors.append("Unexpected availability report identity")
    if report.get("release_sha256") != sha256_file(release_path):
        errors.append("Availability result release hash mismatch")
    if report.get("plan_sha256") != sha256_file(plan_path):
        errors.append("Availability result plan hash mismatch")
    results = report.get("results", [])
    if len(results) != len(plan) or [row.get("availability_plan_id") for row in results] != [row["availability_plan_id"] for row in plan]:
        errors.append("Availability result coverage/order mismatch")
    resolved = 0
    available = 0
    unavailable = 0
    unresolved = 0
    error_counts: Counter[str] = Counter()
    queried = 0
    for source, row in zip(plan, results):
        for field in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url"):
            if row.get(field) != source[field]:
                errors.append(f"Plan/result field mismatch: {source['availability_plan_id']}:{field}")
        if row.get("query_timestamp") != source["target_timestamp"]:
            errors.append(f"Plan/result timestamp mismatch: {source['availability_plan_id']}")
        queried += row.get("queried") is True
        if row.get("error") is not None:
            unresolved += 1
            error_counts[str(row["error"])] += 1
            if row.get("available") is not None:
                errors.append(f"Unresolved result has availability value: {source['availability_plan_id']}")
            continue
        resolved += 1
        if row.get("available") is True:
            available += 1
            if row.get("snapshot_http_status") != "200" or not valid_snapshot_url(str(row.get("snapshot_url") or ""), str(row.get("snapshot_timestamp") or "")):
                errors.append(f"Available result has invalid snapshot evidence: {source['availability_plan_id']}")
        elif row.get("available") is False:
            unavailable += 1
            if any(row.get(key) is not None for key in ("snapshot_timestamp", "snapshot_url", "snapshot_http_status")):
                errors.append(f"Unavailable result retains snapshot evidence: {source['availability_plan_id']}")
        else:
            errors.append(f"Resolved result lacks boolean availability: {source['availability_plan_id']}")
    observed = {
        "requested_candidate_count": len(results), "available_snapshot_count": available,
        "unavailable_snapshot_count": unavailable, "unresolved_error_count": unresolved,
    }
    for key, value in observed.items():
        if report.get(key) != value:
            errors.append(f"Availability aggregate mismatch: {key}")
    if report.get("network_request_count") != queried:
        errors.append("Availability request/queried count mismatch")
    if report.get("stopped_on_http_429") is not True or not any("HTTP 429" in key for key in error_counts):
        errors.append("Availability 429 stop not preserved")
    expected_safety = {"candidate_live_domain_access_operations": 0, "only_archive_availability_hosts_accessed": True, "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    if report.get("safety_contract") != expected_safety:
        errors.append("Availability result safety contract changed")
    result = {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_RESULT_INDEPENDENT_QA_V1",
        "status": "PASS_PARTIAL_ERRORS_PRESERVED_RETRY_ONLY_UNRESOLVED" if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(release_path), "plan_sha256": sha256_file(plan_path), "result_sha256": sha256_file(result_path)},
        "checks": {"candidate_membership_and_order_preserved": not any("coverage/order" in e for e in errors), "resolved_results": resolved, "available_results": available, "unavailable_results": unavailable, "unresolved_results": unresolved, "queried_results": queried, "error_counts": dict(error_counts), "only_unresolved_retry_allowed": not errors},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0},
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite availability QA")
    result = verify(args.release, args.result)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
