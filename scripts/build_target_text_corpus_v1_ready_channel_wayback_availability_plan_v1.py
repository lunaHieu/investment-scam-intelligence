"""Build B3's exact 70-row Wayback availability plan entirely offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_PLAN_RELEASE_V1"
PASS_STATUS = "PASS_EXACT_70_AVAILABILITY_PLAN_MATERIALIZED_NETWORK_CLOSED"
CHANNELS = ("CONFIRMED_REGULATOR_LINKED_WEBSITE", "LEGITIMATE_REGISTER_LINKED_WEBSITE")
COHORTS = ("DEVELOPMENT", "EXTERNAL_HOLDOUT")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def planned_request_url(endpoint: str, candidate_url: str, timestamp: str) -> str:
    endpoint_parts = urllib.parse.urlsplit(endpoint)
    if endpoint_parts.scheme != "https" or endpoint_parts.hostname != "archive.org" or endpoint_parts.path != "/wayback/available":
        raise ValueError("B3 endpoint is not the approved Wayback availability endpoint")
    candidate_parts = urllib.parse.urlsplit(candidate_url)
    if candidate_parts.scheme not in {"http", "https"} or not candidate_parts.hostname:
        raise ValueError("B3 candidate URL is invalid")
    if not re.fullmatch(r"\d{8}", timestamp):
        raise ValueError("B3 target timestamp must be YYYYMMDD")
    return endpoint + "?" + urllib.parse.urlencode({"url": candidate_url, "timestamp": timestamp})


def validate_release(config_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    release = load_object(config_path)
    if release.get("release_id") != RELEASE_ID:
        raise ValueError("Unexpected B3 availability-plan release")
    root = config_path.resolve().parents[1]
    for role, item in release["inputs"].items():
        path = resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"B3 input mismatch: {role}")
    qa = load_object(resolved(root, release["inputs"]["independent_queue_qa"]["path"]))
    if qa.get("status") != release["inputs"]["independent_queue_qa"]["required_status"] or qa.get("errors") != []:
        raise PermissionError("B2 independent queue QA is not PASS")
    for gate in (
        "network_execution_allowed",
        "candidate_live_domain_access_allowed",
        "wayback_query_execution_allowed",
        "archived_page_download_allowed",
        "artifact_capture_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "model_scoring_allowed",
        "training_allowed",
    ):
        if release["decision"].get(gate) is not False:
            raise PermissionError(f"B3 release opened forbidden gate: {gate}")
    contract = release["availability_contract"]
    required = {
        "minimum_delay_seconds_for_future_execution": 60.0,
        "maximum_attempts_per_candidate_for_future_execution": 1,
        "descriptive_user_agent_required": True,
        "partial_journal_reserved_before_network_required": True,
        "automatic_resume_allowed": False,
        "stop_on_http_429": True,
        "preserve_retry_after_and_archive_diagnostics": True,
        "errors_are_not_interpreted_as_no_snapshot": True,
        "archived_page_download_allowed": False,
        "candidate_live_domain_access_allowed": False,
    }
    for field, value in required.items():
        if contract.get(field) != value:
            raise PermissionError(f"B3 future execution guard changed: {field}")
    queue_path = resolved(root, release["inputs"]["candidate_queue"]["path"])
    queue = read_jsonl(queue_path)
    if len(queue) != release["population_contract"]["expected_records"]:
        raise ValueError("B3 queue record count changed")
    return release, queue


def build_rows(config_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    release, queue = validate_release(config_path)
    availability = release["availability_contract"]
    population = release["population_contract"]
    counts: Counter[tuple[str, str]] = Counter()
    plan: list[dict[str, Any]] = []
    candidate_ids: list[str] = []
    hosts: list[str] = []
    entities: list[str] = []
    fingerprints: list[str] = []
    for ordinal, source in enumerate(queue, 1):
        review = source.get("review_state", {})
        safety = source.get("safety", {})
        identity = source.get("candidate_identity", {})
        cohort = str(source.get("cohort"))
        channel = str(source.get("channel_id"))
        candidate_id = str(source.get("candidate_id"))
        host = str(identity.get("normalized_host"))
        entity = str(identity.get("normalized_entity"))
        if cohort not in COHORTS or channel not in CHANNELS:
            raise ValueError(f"B3 queue channel/cohort changed: {candidate_id}")
        if (
            review.get("ground_truth_status") != population["required_ground_truth_status"]
            or review.get("label_created") is not population["required_label_created"]
            or review.get("training_eligible") != population["required_training_eligible"]
            or safety.get("wayback_queried") is not False
            or safety.get("live_domain_accessed") is not False
            or safety.get("artifact_captured") is not False
        ):
            raise PermissionError(f"B3 source row is no longer untouched and uncertain: {candidate_id}")
        host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
        if identity.get("normalized_host_sha256") != host_hash:
            raise ValueError(f"B3 source host hash mismatch: {candidate_id}")
        reference_observed_at = str(source["reference"]["reference_observed_at"])
        if not reference_observed_at.startswith("2026-10-03"):
            raise ValueError(f"B3 target timestamp basis changed: {candidate_id}")
        plan_id = f"TTCV1_B3_AVAIL_{ordinal:03d}"
        request_url = planned_request_url(availability["endpoint"], identity["candidate_url"], availability["target_timestamp"])
        row = {
            "schema_version": "target_text_corpus_v1_ready_channel_wayback_availability_plan_v1",
            "availability_plan_id": plan_id,
            "candidate_id": candidate_id,
            "enumeration_wave_id": source["enumeration_wave_id"],
            "cohort": cohort,
            "channel_id": channel,
            "channel_target_stratum": source["channel_target_stratum"],
            "candidate_host": host,
            "candidate_host_sha256": host_hash,
            "normalized_entity": entity,
            "candidate_url": identity["candidate_url"],
            "reference_source_id": source["reference"]["source_id"],
            "reference_source_record_id": source["reference"]["source_record_id"],
            "reference_observed_at": reference_observed_at,
            "target_timestamp": availability["target_timestamp"],
            "availability_endpoint": availability["endpoint"],
            "planned_request_url": request_url,
            "plan_status": "PLANNED_NOT_EXECUTED",
            "wayback_queried": False,
            "candidate_live_domain_accessed": False,
            "archived_page_downloaded": False,
            "artifact_captured": False,
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "model_scored": False,
            "training_eligible": "NO",
        }
        plan.append(row)
        candidate_ids.append(candidate_id)
        hosts.append(host)
        entities.append(entity)
        counts[(channel, cohort)] += 1
        fingerprints.append(f"{plan_id}|{candidate_id}|{cohort}|{channel}|{host}|{availability['target_timestamp']}")
    expected_counts = {
        (channel, cohort): (25 if cohort == "DEVELOPMENT" else 10)
        for cohort in COHORTS
        for channel in CHANNELS
    }
    if dict(counts) != expected_counts:
        raise ValueError("B3 channel/cohort counts changed")
    if len(set(candidate_ids)) != 70 or len(set(hosts)) != 70 or len(set(entities)) != 70:
        raise ValueError("B3 candidate/host/entity disjointness failed")
    dev_hosts = {row["candidate_host"] for row in plan if row["cohort"] == "DEVELOPMENT"}
    holdout_hosts = {row["candidate_host"] for row in plan if row["cohort"] == "EXTERNAL_HOLDOUT"}
    dev_entities = {row["normalized_entity"] for row in plan if row["cohort"] == "DEVELOPMENT"}
    holdout_entities = {row["normalized_entity"] for row in plan if row["cohort"] == "EXTERNAL_HOLDOUT"}
    if dev_hosts & holdout_hosts or dev_entities & holdout_entities:
        raise ValueError("B3 development/holdout overlap detected")
    report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_PLAN_REPORT_V1",
        "status": PASS_STATUS,
        "release_sha256": sha256_file(config_path),
        "plan_fingerprint": hashlib.sha256("\n".join(fingerprints).encode("utf-8")).hexdigest(),
        "population": {
            "records": len(plan),
            "development_records": sum(row["cohort"] == "DEVELOPMENT" for row in plan),
            "external_holdout_records": sum(row["cohort"] == "EXTERNAL_HOLDOUT" for row in plan),
            "counts": {channel: {cohort: counts[(channel, cohort)] for cohort in COHORTS} for channel in CHANNELS},
            "unique_candidate_ids": len(set(candidate_ids)),
            "unique_hosts": len(set(hosts)),
            "unique_normalized_entities": len(set(entities)),
            "development_holdout_host_overlap": 0,
            "development_holdout_entity_overlap": 0,
        },
        "future_execution_contract": availability,
        "operations": {"network": 0, "candidate_domain_access": 0, "wayback_queries": 0, "archived_page_downloads": 0, "captures": 0, "labels": 0, "model": 0},
        "decision": {"plan_materialized": True, "independent_plan_qa_required": True, "b4_execution_release_preparation_allowed": False, "network_execution_allowed": False, "capture_allowed": False, "labeling_allowed": False, "training_allowed": False},
    }
    return plan, report


def materialize(config_path: Path) -> dict[str, Any]:
    release = load_object(config_path)
    output = Path(release["outputs"]["directory"])
    staging = output.with_name(output.name + ".partial")
    if output.exists() or staging.exists():
        raise FileExistsError("Refusing to overwrite B3 availability-plan output")
    plan, report = build_rows(config_path)
    staging.mkdir(parents=True)
    try:
        plan_path = staging / release["outputs"]["plan_filename"]
        report_path = staging / release["outputs"]["report_filename"]
        plan_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in plan), encoding="utf-8")
        report["plan_sha256"] = sha256_file(plan_path)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.replace(output)
        return {"status": report["status"], "records": len(plan), "plan_sha256": report["plan_sha256"], "report_sha256": sha256_file(output / release["outputs"]["report_filename"]), "output_directory": str(output)}
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        plan, report = build_rows(args.config)
        print(json.dumps({"status": report["status"], "records": len(plan), "population": report["population"], "decision": report["decision"]}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(materialize(args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
