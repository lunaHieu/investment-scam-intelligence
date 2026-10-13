"""Build a bounded no-network Wayback availability plan for reviewed SEC/IAPD rows."""

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
from src.isi.normalization.external_references import canonicalize_host


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def archive_query_url(endpoint: str, candidate_url: str, timestamp: str) -> str:
    endpoint_parts = urllib.parse.urlparse(endpoint)
    if endpoint_parts.scheme != "https" or endpoint_parts.hostname != "archive.org" or endpoint_parts.path != "/wayback/available":
        raise ValueError("Availability plan endpoint is not the approved archive endpoint")
    candidate_parts = urllib.parse.urlparse(candidate_url)
    if candidate_parts.scheme not in {"http", "https"} or not candidate_parts.hostname:
        raise ValueError("Availability plan contains invalid candidate URL")
    if not re.fullmatch(r"\d{8}", timestamp):
        raise ValueError("Availability target timestamp must be YYYYMMDD")
    return endpoint + "?" + urllib.parse.urlencode({"url": candidate_url, "timestamp": timestamp})


def plan_id(cohort: str, rank: int) -> str:
    prefix = "TTCV1_EDGAR_AVAIL_DEV" if cohort == "DEVELOPMENT" else "TTCV1_EDGAR_AVAIL_HOLDOUT"
    return f"{prefix}_{rank:03d}"


def remove_staging(staging: Path, output: Path) -> None:
    if not staging.exists():
        return
    if staging.resolve().parent != output.resolve().parent or staging.name != output.name + ".partial":
        raise RuntimeError("Refusing to remove unexpected availability-plan staging directory")
    shutil.rmtree(staging)


def validate_config(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_PLAN_V1":
        raise ValueError("Unexpected SEC/IAPD Wayback availability-plan protocol")
    root = config_path.resolve().parents[1]
    for item in config["basis"]:
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Availability-plan basis mismatch: {item['role']}")
    for item in config["inputs"].values():
        path = Path(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError("Availability-plan input hash mismatch")
    verification = load_object(Path(config["inputs"]["independent_verification"]["path"]))
    if verification.get("status") != config["inputs"]["independent_verification"]["required_status"]:
        raise ValueError("Offline review independent verification did not pass")
    decision = config["decision"]
    if decision.get("plan_materialization_allowed") is not True:
        raise PermissionError("Availability-plan materialization is closed")
    for gate in ("wayback_availability_query_execution_allowed", "candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            raise PermissionError(f"Availability plan opened forbidden gate: {gate}")
    return config


def build(config_path: Path) -> dict[str, Any]:
    config = validate_config(config_path)
    output = Path(config["outputs"]["directory"])
    staging = output.with_name(output.name + ".partial")
    if output.exists() or staging.exists():
        raise FileExistsError("Refusing to overwrite Wayback availability-plan output")
    staging.mkdir(parents=True)
    try:
        shortlist = load_jsonl(Path(config["inputs"]["shortlist"]["path"]))
        review = load_jsonl(Path(config["inputs"]["offline_review"]["path"]))
        if len(shortlist) != config["inputs"]["shortlist"]["record_count"] or len(review) != config["inputs"]["offline_review"]["record_count"]:
            raise ValueError("Availability-plan input count mismatch")
        review_by_id = {row["shortlist_id"]: row for row in review}
        if len(review_by_id) != len(review) or set(review_by_id) != {row["shortlist_id"] for row in shortlist}:
            raise ValueError("Availability-plan review coverage mismatch")
        required = config["population_contract"]["required_recommendation"]
        excluded = config["population_contract"]["excluded_recommendation"]
        eligible = [row for row in shortlist if review_by_id[row["shortlist_id"]]["future_capture_planning_recommendation"] == required]
        held = [row for row in shortlist if review_by_id[row["shortlist_id"]]["future_capture_planning_recommendation"] == excluded]
        if len(eligible) != config["population_contract"]["expected_plan_rows"] or len(held) != config["population_contract"]["expected_excluded_caution_rows"]:
            raise ValueError("Availability-plan eligible or held count mismatch")
        if len(eligible) + len(held) != len(shortlist):
            raise ValueError("Availability-plan review recommendation is outside the frozen contract")
        endpoint = config["availability_contract"]["endpoint"]
        timestamp = config["availability_contract"]["target_timestamp"]
        ranks = Counter()
        plan: list[dict[str, Any]] = []
        for row in eligible:
            review_row = review_by_id[row["shortlist_id"]]
            host = canonicalize_host(row["candidate_url"])
            if not host or host != row["normalized_host"] or hashlib.sha256(host.encode()).hexdigest() != row["normalized_host_sha256"]:
                raise ValueError("Availability-plan candidate URL/host mismatch")
            if review_row["identity_review_status"] not in {"OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS", "OFFLINE_COMPATIBLE_NAME_VARIANT_EVIDENCE_PASS"}:
                raise ValueError("Availability-plan row lacks passing identity evidence")
            ranks[row["cohort"]] += 1
            plan.append({
                "availability_plan_id": plan_id(row["cohort"], ranks[row["cohort"]]),
                "shortlist_id": row["shortlist_id"],
                "cohort": row["cohort"],
                "acquisition_wave_id": row["acquisition_wave_id"],
                "channel_id": row["channel_id"],
                "cik": row["cik"],
                "iapd_source_record_id": row["iapd_source_record_id"],
                "candidate_host": host,
                "candidate_url": row["candidate_url"],
                "identity_review_status": review_row["identity_review_status"],
                "target_timestamp": timestamp,
                "availability_endpoint": endpoint,
                "planned_request_url": archive_query_url(endpoint, row["candidate_url"], timestamp),
                "plan_status": "PLANNED_NOT_EXECUTED",
                "wayback_queried": False,
                "candidate_live_domain_accessed": False,
                "archived_page_downloaded": False,
                "artifact_captured": False,
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            })
        expected_counts = {
            "DEVELOPMENT": config["population_contract"]["expected_development_rows"],
            "EXTERNAL_HOLDOUT": config["population_contract"]["expected_external_holdout_rows"],
        }
        if dict(ranks) != expected_counts:
            raise ValueError("Availability-plan cohort counts mismatch")
        hosts = [row["candidate_host"] for row in plan]
        ids = [row["shortlist_id"] for row in plan]
        if len(hosts) != len(set(hosts)) or len(ids) != len(set(ids)):
            raise ValueError("Availability-plan host or shortlist ID is duplicated")
        dev_hosts = {row["candidate_host"] for row in plan if row["cohort"] == "DEVELOPMENT"}
        holdout_hosts = {row["candidate_host"] for row in plan if row["cohort"] == "EXTERNAL_HOLDOUT"}
        if dev_hosts & holdout_hosts:
            raise ValueError("Availability-plan cohorts overlap by host")
        plan_path = staging / config["outputs"]["plan_filename"]
        plan_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in plan), encoding="utf-8")
        fingerprint = hashlib.sha256("\n".join(f"{row['availability_plan_id']}|{row['shortlist_id']}|{row['candidate_host']}|{row['target_timestamp']}" for row in plan).encode()).hexdigest()
        report = {
            "analysis_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_WAYBACK_AVAILABILITY_PLAN_V1",
            "status": "FROZEN_BOUNDED_DISJOINT_PLAN_NOT_EXECUTED",
            "output": {"plan_filename": plan_path.name, "plan_sha256": sha256_file(plan_path), "plan_fingerprint": fingerprint, "plan_rows": len(plan)},
            "population": {"development_rows": ranks["DEVELOPMENT"], "external_holdout_rows": ranks["EXTERNAL_HOLDOUT"], "excluded_caution_rows": len(held), "unique_candidate_hosts": len(set(hosts)), "cross_cohort_host_overlap": 0},
            "execution": {"wayback_availability_requests": 0, "candidate_live_domain_requests": 0, "archived_page_downloads": 0, "artifact_captures": 0, "labels_created": 0, "network_execution_allowed": False},
            "decision": {"plan_materialization_passed": True, "query_execution_requires_separate_release": True, "capture_allowed": False, "training_allowed": False},
        }
        report_path = staging / config["outputs"]["report_filename"]
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.replace(output)
        report["output_directory"] = str(output)
        return report
    except Exception:
        remove_staging(staging, output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
