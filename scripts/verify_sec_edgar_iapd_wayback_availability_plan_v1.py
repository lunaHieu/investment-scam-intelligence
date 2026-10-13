"""Independently verify the bounded SEC/IAPD Wayback availability plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.normalization.external_references import canonicalize_host


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def expected_plan_id(cohort: str, rank: int) -> str:
    if cohort == "DEVELOPMENT":
        return f"TTCV1_EDGAR_AVAIL_DEV_{rank:03d}"
    if cohort == "EXTERNAL_HOLDOUT":
        return f"TTCV1_EDGAR_AVAIL_HOLDOUT_{rank:03d}"
    raise ValueError("Unexpected availability-plan cohort")


def decode_planned_request(value: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "archive.org" or parsed.path != "/wayback/available":
        raise ValueError("Planned request targets a non-approved endpoint")
    query = urllib.parse.parse_qs(parsed.query, strict_parsing=True)
    if set(query) != {"url", "timestamp"} or len(query["url"]) != 1 or len(query["timestamp"]) != 1:
        raise ValueError("Planned request query shape changed")
    if not re.fullmatch(r"\d{8}", query["timestamp"][0]):
        raise ValueError("Planned request timestamp is malformed")
    return query["url"][0], query["timestamp"][0]


def verify(config_path: Path, output_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_PLAN_V1":
        raise ValueError("Unexpected availability-plan protocol")
    root = config_path.resolve().parents[1]
    for item in config["basis"]:
        if sha256_file(root / item["path"]) != item["sha256"]:
            raise ValueError(f"Independent availability-plan basis mismatch: {item['role']}")
    for item in config["inputs"].values():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("Independent availability-plan input mismatch")
    verification = load_object(Path(config["inputs"]["independent_verification"]["path"]))
    if verification.get("status") != "PASS":
        raise ValueError("Independent offline-review prerequisite is not PASS")
    for gate in ("wayback_availability_query_execution_allowed", "candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if config["decision"].get(gate) is not False:
            raise PermissionError(f"Independent availability-plan verification found open gate: {gate}")

    shortlist = read_jsonl(Path(config["inputs"]["shortlist"]["path"]))
    review = read_jsonl(Path(config["inputs"]["offline_review"]["path"]))
    review_by_id = {row["shortlist_id"]: row for row in review}
    required = config["population_contract"]["required_recommendation"]
    excluded = config["population_contract"]["excluded_recommendation"]
    expected = [row for row in shortlist if review_by_id[row["shortlist_id"]]["future_capture_planning_recommendation"] == required]
    held = [row for row in shortlist if review_by_id[row["shortlist_id"]]["future_capture_planning_recommendation"] == excluded]
    if len(expected) != config["population_contract"]["expected_plan_rows"] or len(held) != config["population_contract"]["expected_excluded_caution_rows"]:
        raise ValueError("Independent availability-plan population reproduction failed")

    plan_dir = Path(config["outputs"]["directory"])
    plan_path = plan_dir / config["outputs"]["plan_filename"]
    report_path = plan_dir / config["outputs"]["report_filename"]
    plan = read_jsonl(plan_path)
    report = load_object(report_path)
    if len(plan) != len(expected):
        raise ValueError("Independent availability-plan coverage mismatch")
    if [row["shortlist_id"] for row in plan] != [row["shortlist_id"] for row in expected]:
        raise ValueError("Independent availability-plan selection or order mismatch")
    expected_fields = {
        "availability_plan_id", "shortlist_id", "cohort", "acquisition_wave_id", "channel_id", "cik",
        "iapd_source_record_id", "candidate_host", "candidate_url", "identity_review_status",
        "target_timestamp", "availability_endpoint", "planned_request_url", "plan_status", "wayback_queried",
        "candidate_live_domain_accessed", "archived_page_downloaded", "artifact_captured",
        "ground_truth_status", "label_created", "training_eligible",
    }
    ranks: Counter[str] = Counter()
    fingerprints: list[str] = []
    for actual, source in zip(plan, expected):
        if set(actual) != expected_fields:
            raise ValueError("Independent availability-plan schema check failed")
        ranks[source["cohort"]] += 1
        if actual["availability_plan_id"] != expected_plan_id(source["cohort"], ranks[source["cohort"]]):
            raise ValueError("Independent availability-plan ID check failed")
        for field in ("shortlist_id", "cohort", "acquisition_wave_id", "channel_id", "cik", "iapd_source_record_id", "candidate_url"):
            if actual[field] != source[field]:
                raise ValueError("Independent availability-plan source-field check failed")
        host = canonicalize_host(source["candidate_url"])
        if not host or actual["candidate_host"] != host or host != source["normalized_host"]:
            raise ValueError("Independent availability-plan host check failed")
        decoded_url, decoded_timestamp = decode_planned_request(actual["planned_request_url"])
        if decoded_url != source["candidate_url"] or decoded_timestamp != config["availability_contract"]["target_timestamp"]:
            raise ValueError("Independent planned-request decoding failed")
        if actual["availability_endpoint"] != config["availability_contract"]["endpoint"] or actual["target_timestamp"] != decoded_timestamp:
            raise ValueError("Independent availability endpoint/timestamp check failed")
        review_row = review_by_id[source["shortlist_id"]]
        if actual["identity_review_status"] != review_row["identity_review_status"]:
            raise ValueError("Independent availability identity-state check failed")
        if actual["plan_status"] != "PLANNED_NOT_EXECUTED" or actual["ground_truth_status"] != "UNCERTAIN" or actual["training_eligible"] != "NO":
            raise ValueError("Independent availability-plan state check failed")
        for field in ("wayback_queried", "candidate_live_domain_accessed", "archived_page_downloaded", "artifact_captured", "label_created"):
            if actual[field] is not False:
                raise ValueError("Independent availability-plan closed-state check failed")
        fingerprints.append(f"{actual['availability_plan_id']}|{actual['shortlist_id']}|{actual['candidate_host']}|{actual['target_timestamp']}")

    host_values = [row["candidate_host"] for row in plan]
    if len(host_values) != len(set(host_values)):
        raise ValueError("Independent availability-plan unique-host check failed")
    dev = {row["candidate_host"] for row in plan if row["cohort"] == "DEVELOPMENT"}
    holdout = {row["candidate_host"] for row in plan if row["cohort"] == "EXTERNAL_HOLDOUT"}
    if dev & holdout:
        raise ValueError("Independent availability-plan cohort disjointness failed")
    held_ids = {row["shortlist_id"] for row in held}
    if held_ids & {row["shortlist_id"] for row in plan}:
        raise ValueError("Independent availability-plan caution exclusion failed")
    fingerprint = hashlib.sha256("\n".join(fingerprints).encode()).hexdigest()
    if report["output"]["plan_sha256"] != sha256_file(plan_path) or report["output"]["plan_fingerprint"] != fingerprint:
        raise ValueError("Independent availability-plan report fingerprint mismatch")
    expected_counts = {"DEVELOPMENT": config["population_contract"]["expected_development_rows"], "EXTERNAL_HOLDOUT": config["population_contract"]["expected_external_holdout_rows"]}
    if dict(ranks) != expected_counts or report["population"]["excluded_caution_rows"] != len(held):
        raise ValueError("Independent availability-plan cohort/count report mismatch")
    if report["execution"] != {"wayback_availability_requests": 0, "candidate_live_domain_requests": 0, "archived_page_downloads": 0, "artifact_captures": 0, "labels_created": 0, "network_execution_allowed": False}:
        raise ValueError("Independent availability-plan execution state changed")

    result = {
        "verification_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_PLAN_INDEPENDENT_VERIFICATION_V1",
        "status": "PASS",
        "config_sha256": sha256_file(config_path),
        "plan_sha256": sha256_file(plan_path),
        "report_sha256": sha256_file(report_path),
        "checks": {
            "eligible_population_exactly_reproduced": True,
            "plan_rows": len(plan),
            "development_rows": ranks["DEVELOPMENT"],
            "external_holdout_rows": ranks["EXTERNAL_HOLDOUT"],
            "caution_rows_excluded": len(held),
            "unique_candidate_hosts": len(set(host_values)),
            "cross_cohort_host_overlap": 0,
            "planned_request_urls_decode_exactly": True,
            "network_execution_allowed": False,
        },
        "operations": {"network": 0, "candidate_domain_access": 0, "wayback_queries": 0, "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0},
    }
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite independent availability-plan verification")
    temporary = output_path.with_suffix(output_path.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.config, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
