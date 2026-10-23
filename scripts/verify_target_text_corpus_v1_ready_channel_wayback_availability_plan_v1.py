"""Independently verify B3's exact offline Wayback availability plan."""

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


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_PLAN_RELEASE_V1"
PASS_STATUS = "PASS_EXACT_70_AVAILABILITY_PLAN_INDEPENDENTLY_REPRODUCED_NETWORK_CLOSED"
EXPECTED_FIELDS = {
    "schema_version", "availability_plan_id", "candidate_id", "enumeration_wave_id", "cohort",
    "channel_id", "channel_target_stratum", "candidate_host", "candidate_host_sha256",
    "normalized_entity", "candidate_url", "reference_source_id", "reference_source_record_id",
    "reference_observed_at", "target_timestamp", "availability_endpoint", "planned_request_url",
    "plan_status", "wayback_queried", "candidate_live_domain_accessed", "archived_page_downloaded",
    "artifact_captured", "ground_truth_status", "label_created", "model_scored", "training_eligible",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def decode_request(value: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != "archive.org" or parsed.path != "/wayback/available" or parsed.fragment:
        raise ValueError("Planned B3 request targets a non-approved endpoint")
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    if set(query) != {"url", "timestamp"} or any(len(values) != 1 for values in query.values()):
        raise ValueError("Planned B3 request query shape changed")
    timestamp = query["timestamp"][0]
    if not re.fullmatch(r"\d{8}", timestamp):
        raise ValueError("Planned B3 request timestamp is malformed")
    return query["url"][0], timestamp


def verify(config_path: Path, plan_path: Path, report_path: Path) -> dict[str, Any]:
    release = load_object(config_path)
    root = config_path.resolve().parents[1]
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected B3 release identity")
    for role, item in release.get("inputs", {}).items():
        path = resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"B3 input mismatch: {role}")
    for gate in (
        "network_execution_allowed", "candidate_live_domain_access_allowed", "wayback_query_execution_allowed",
        "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed",
        "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed",
    ):
        if release.get("decision", {}).get(gate) is not False:
            errors.append(f"B3 forbidden gate opened: {gate}")
    future = release.get("availability_contract", {})
    if float(future.get("minimum_delay_seconds_for_future_execution", 0)) < 60.0:
        errors.append("B3 future pacing is below 60 seconds")
    for field, expected in (
        ("maximum_attempts_per_candidate_for_future_execution", 1),
        ("descriptive_user_agent_required", True),
        ("partial_journal_reserved_before_network_required", True),
        ("automatic_resume_allowed", False),
        ("stop_on_http_429", True),
        ("preserve_retry_after_and_archive_diagnostics", True),
        ("errors_are_not_interpreted_as_no_snapshot", True),
        ("archived_page_download_allowed", False),
        ("candidate_live_domain_access_allowed", False),
    ):
        if future.get(field) != expected:
            errors.append(f"B3 future execution guard changed: {field}")

    queue_path = resolved(root, release["inputs"]["candidate_queue"]["path"])
    queue = read_jsonl(queue_path) if queue_path.is_file() else []
    plan = read_jsonl(plan_path) if plan_path.is_file() else []
    report = load_object(report_path) if report_path.is_file() else {}
    if len(queue) != 70 or len(plan) != 70:
        errors.append("B3 queue or plan does not contain exactly 70 rows")

    counts: Counter[tuple[str, str]] = Counter()
    plan_ids: list[str] = []
    candidate_ids: list[str] = []
    hosts: list[str] = []
    entities: list[str] = []
    fingerprints: list[str] = []
    for ordinal, pair in enumerate(zip(queue, plan), 1):
        source, actual = pair
        candidate_id = str(source.get("candidate_id"))
        expected_plan_id = f"TTCV1_B3_AVAIL_{ordinal:03d}"
        if set(actual) != EXPECTED_FIELDS:
            errors.append(f"B3 plan schema changed: {expected_plan_id}")
            continue
        identity = source["candidate_identity"]
        reference = source["reference"]
        direct_fields = {
            "availability_plan_id": expected_plan_id,
            "candidate_id": candidate_id,
            "enumeration_wave_id": source["enumeration_wave_id"],
            "cohort": source["cohort"],
            "channel_id": source["channel_id"],
            "channel_target_stratum": source["channel_target_stratum"],
            "candidate_host": identity["normalized_host"],
            "candidate_host_sha256": identity["normalized_host_sha256"],
            "normalized_entity": identity["normalized_entity"],
            "candidate_url": identity["candidate_url"],
            "reference_source_id": reference["source_id"],
            "reference_source_record_id": reference["source_record_id"],
            "reference_observed_at": reference["reference_observed_at"],
            "target_timestamp": future["target_timestamp"],
            "availability_endpoint": future["endpoint"],
        }
        for field, value in direct_fields.items():
            if actual.get(field) != value:
                errors.append(f"B3 plan/source mismatch: {expected_plan_id}:{field}")
        expected_host_hash = hashlib.sha256(actual["candidate_host"].encode("utf-8")).hexdigest()
        if actual["candidate_host_sha256"] != expected_host_hash:
            errors.append(f"B3 host hash mismatch: {expected_plan_id}")
        try:
            decoded_url, decoded_timestamp = decode_request(actual["planned_request_url"])
            if decoded_url != actual["candidate_url"] or decoded_timestamp != actual["target_timestamp"]:
                errors.append(f"B3 request URL does not round-trip: {expected_plan_id}")
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"B3 request URL invalid: {expected_plan_id}: {error}")
        if actual["plan_status"] != "PLANNED_NOT_EXECUTED" or actual["ground_truth_status"] != "UNCERTAIN" or actual["training_eligible"] != "NO":
            errors.append(f"B3 plan state changed: {expected_plan_id}")
        for field in ("wayback_queried", "candidate_live_domain_accessed", "archived_page_downloaded", "artifact_captured", "label_created", "model_scored"):
            if actual[field] is not False:
                errors.append(f"B3 operation already performed: {expected_plan_id}:{field}")
        plan_ids.append(actual["availability_plan_id"])
        candidate_ids.append(actual["candidate_id"])
        hosts.append(actual["candidate_host"])
        entities.append(actual["normalized_entity"])
        counts[(actual["channel_id"], actual["cohort"])] += 1
        fingerprints.append(f"{actual['availability_plan_id']}|{actual['candidate_id']}|{actual['cohort']}|{actual['channel_id']}|{actual['candidate_host']}|{actual['target_timestamp']}")

    expected_counts = {
        (channel, cohort): (25 if cohort == "DEVELOPMENT" else 10)
        for cohort in ("DEVELOPMENT", "EXTERNAL_HOLDOUT")
        for channel in ("CONFIRMED_REGULATOR_LINKED_WEBSITE", "LEGITIMATE_REGISTER_LINKED_WEBSITE")
    }
    if dict(counts) != expected_counts:
        errors.append("B3 channel/cohort counts changed")
    if any(len(values) != 70 for values in (set(plan_ids), set(candidate_ids), set(hosts), set(entities))):
        errors.append("B3 plan IDs, candidates, hosts, or entities are not globally unique")
    development_hosts = {row.get("candidate_host") for row in plan if row.get("cohort") == "DEVELOPMENT"}
    holdout_hosts = {row.get("candidate_host") for row in plan if row.get("cohort") == "EXTERNAL_HOLDOUT"}
    development_entities = {row.get("normalized_entity") for row in plan if row.get("cohort") == "DEVELOPMENT"}
    holdout_entities = {row.get("normalized_entity") for row in plan if row.get("cohort") == "EXTERNAL_HOLDOUT"}
    if development_hosts & holdout_hosts or development_entities & holdout_entities:
        errors.append("B3 development/holdout disjointness failed")

    fingerprint = hashlib.sha256("\n".join(fingerprints).encode("utf-8")).hexdigest()
    if report.get("status") != "PASS_EXACT_70_AVAILABILITY_PLAN_MATERIALIZED_NETWORK_CLOSED":
        errors.append("B3 plan report status changed")
    if report.get("release_sha256") != sha256_file(config_path) or report.get("plan_sha256") != sha256_file(plan_path) or report.get("plan_fingerprint") != fingerprint:
        errors.append("B3 plan report hash or fingerprint mismatch")
    expected_operations = {"network": 0, "candidate_domain_access": 0, "wayback_queries": 0, "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0}
    if report.get("operations") != expected_operations:
        errors.append("B3 plan report operations changed")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_PLAN_INDEPENDENT_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "inputs": {"release_sha256": sha256_file(config_path), "queue_sha256": sha256_file(queue_path), "plan_sha256": sha256_file(plan_path), "report_sha256": sha256_file(report_path)},
        "checks": {
            "plan_rows": len(plan),
            "development_rows": sum(row.get("cohort") == "DEVELOPMENT" for row in plan),
            "external_holdout_rows": sum(row.get("cohort") == "EXTERNAL_HOLDOUT" for row in plan),
            "unique_plan_ids": len(set(plan_ids)),
            "unique_candidate_ids": len(set(candidate_ids)),
            "unique_hosts": len(set(hosts)),
            "unique_normalized_entities": len(set(entities)),
            "development_holdout_host_overlap": len(development_hosts & holdout_hosts),
            "development_holdout_entity_overlap": len(development_entities & holdout_entities),
            "candidate_order_preserved": [row.get("candidate_id") for row in plan] == [row.get("candidate_id") for row in queue],
            "planned_request_urls_round_trip": not any("request URL" in error for error in errors),
            "future_minimum_delay_seconds": future.get("minimum_delay_seconds_for_future_execution"),
            "network_operations": 0,
            "wayback_queries": 0,
            "captures": 0,
            "labels_created": 0,
            "model_operations": 0,
        },
        "decision": {"b3_complete": not errors, "b4_crash_safe_execution_release_preparation_allowed": not errors, "network_execution_allowed": False, "artifact_capture_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release = load_object(args.config)
    directory = Path(release["outputs"]["directory"])
    result = verify(args.config, args.plan or directory / release["outputs"]["plan_filename"], args.report or directory / release["outputs"]["report_filename"])
    if result["status"] == "FAIL":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite B3 independent plan QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
