"""Independently recompute and verify B2's exact 70-row offline provenance queue."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_ready_channel_enumeration_release_v1 import verify as verify_b1
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.curation.target_text_candidate_enumeration import _normalized_entity, _validate_reference_record


EXPECTED_CHANNELS = (
    "CONFIRMED_REGULATOR_LINKED_WEBSITE",
    "LEGITIMATE_REGISTER_LINKED_WEBSITE",
)
EXPECTED_COHORTS = ("DEVELOPMENT", "EXTERNAL_HOLDOUT")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def selection_key(seed: str, namespace: str, channel: str, row: dict[str, Any]) -> str:
    material = "|".join(
        (
            seed,
            namespace,
            channel,
            str(row["source_id"]),
            str(row["source_record_id"]),
            str(row["normalized_host"]),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def independently_recompute_identities(config_path: Path) -> list[tuple[str, str, str, str, str]]:
    release = load_object(config_path)
    root = config_path.resolve().parents[1]
    inputs = {item["role"]: item for item in release["inputs"]}
    for item in inputs.values():
        path = resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"B2 verifier input mismatch: {item['role']}")

    b1_path = resolved(root, inputs["b1_release"]["path"])
    b1_result = verify_b1(b1_path)
    if b1_result["status"] != "PASS_TWO_READY_CHANNELS_CAPACITY_SUFFICIENT_QUEUE_MAY_BE_MATERIALIZED":
        raise PermissionError("B1 preflight no longer authorizes B2")
    b1 = load_object(b1_path)
    exclusion_paths = {item["role"]: Path(item["path"]) for item in b1["exclusion_inputs"]}
    prior_hosts = {
        str(row["candidate_identity"]["normalized_host"]).casefold().rstrip(".")
        for row in read_jsonl(exclusion_paths["prior_four_channel_pilot_queue"])
    }
    prior_hosts.update(
        str(row["candidate_host"]).casefold().rstrip(".")
        for row in read_jsonl(exclusion_paths["prior_sec_iapd_availability_population"])
    )
    opened = load_object(exclusion_paths["opened_external_exclusion_index"])
    opened_hashes = {str(row["normalized_host_sha256"]) for row in opened["records"]}
    target_status = {item["channel_id"]: item["target_status"] for item in b1["channels"]}

    eligible: dict[str, list[dict[str, Any]]] = {}
    for channel_item in b1["channels"]:
        channel = channel_item["channel_id"]
        accepted: list[dict[str, Any]] = []
        channel_hosts: set[str] = set()
        channel_refs: set[tuple[str, str]] = set()
        for source in read_jsonl(Path(channel_item["pool_path"])):
            if _validate_reference_record(channel, source):
                continue
            host = str(source["normalized_host"]).casefold().rstrip(".")
            ref = (str(source["source_id"]), str(source["source_record_id"]))
            host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
            if host in prior_hosts or host_hash in opened_hashes or host in channel_hosts or ref in channel_refs:
                continue
            normalized = dict(source)
            normalized["normalized_host"] = host
            normalized["normalized_entity"] = _normalized_entity(source["entity_name_from_reference"])
            accepted.append(normalized)
            channel_hosts.add(host)
            channel_refs.add(ref)
        eligible[channel] = accepted

    host_membership: defaultdict[str, set[str]] = defaultdict(set)
    entity_strata: defaultdict[str, set[str]] = defaultdict(set)
    for channel, rows in eligible.items():
        for row in rows:
            host_membership[row["normalized_host"]].add(channel)
            if row["normalized_entity"]:
                entity_strata[row["normalized_entity"]].add(target_status[channel])
    forbidden_hosts = {host for host, memberships in host_membership.items() if len(memberships) > 1}
    forbidden_entities = {entity for entity, strata in entity_strata.items() if len(strata) > 1}
    for channel in tuple(eligible):
        eligible[channel] = [
            row
            for row in eligible[channel]
            if row["normalized_host"] not in forbidden_hosts and row["normalized_entity"] not in forbidden_entities
        ]

    population = release["population_contract"]
    wave = b1["wave_contract"]
    selected_hosts: set[str] = set()
    selected_entities: set[str] = set()
    identities: list[tuple[str, str, str, str, str]] = []
    selection_contract = (
        ("DEVELOPMENT", wave["development_namespace"], population["development_per_channel"]),
        ("EXTERNAL_HOLDOUT", wave["external_holdout_namespace"], population["external_holdout_per_channel"]),
    )
    for cohort, namespace, quota in selection_contract:
        for channel in population["channels"]:
            ordered = sorted(
                eligible[channel],
                key=lambda row: selection_key(wave["selection_seed"], namespace, channel, row),
            )
            chosen: list[dict[str, Any]] = []
            chosen_entities: set[str] = set()
            for row in ordered:
                if (
                    row["normalized_host"] in selected_hosts
                    or row["normalized_entity"] in selected_entities
                    or row["normalized_entity"] in chosen_entities
                ):
                    continue
                chosen.append(row)
                chosen_entities.add(row["normalized_entity"])
                if len(chosen) == quota:
                    break
            if len(chosen) != quota:
                raise ValueError(f"Independent B2 recomputation shortfall: {cohort}/{channel}")
            for row in chosen:
                identities.append(
                    (
                        cohort,
                        channel,
                        str(row["source_id"]),
                        str(row["source_record_id"]),
                        str(row["normalized_host"]),
                    )
                )
                selected_hosts.add(row["normalized_host"])
                selected_entities.add(row["normalized_entity"])
    return identities


def verify(config_path: Path, queue_path: Path, report_path: Path) -> dict[str, Any]:
    release = load_object(config_path)
    queue = read_jsonl(queue_path)
    report = load_object(report_path)
    errors: list[str] = []
    if release.get("release_id") != "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_QUEUE_RELEASE_V1":
        errors.append("Unexpected B2 release identity")
    expected_identities = independently_recompute_identities(config_path)
    actual_identities = [
        (
            str(row.get("cohort")),
            str(row.get("channel_id")),
            str(row.get("reference", {}).get("source_id")),
            str(row.get("reference", {}).get("source_record_id")),
            str(row.get("candidate_identity", {}).get("normalized_host")),
        )
        for row in queue
    ]
    if actual_identities != expected_identities:
        errors.append("Queue membership or deterministic order differs from independent recomputation")

    counts: Counter[tuple[str, str]] = Counter()
    ids: list[str] = []
    hosts: list[str] = []
    entities: list[str] = []
    for row in queue:
        channel = str(row.get("channel_id"))
        cohort = str(row.get("cohort"))
        counts[(channel, cohort)] += 1
        ids.append(str(row.get("candidate_id")))
        identity = row.get("candidate_identity", {})
        host = str(identity.get("normalized_host", ""))
        entity = str(identity.get("normalized_entity", ""))
        hosts.append(host)
        entities.append(entity)
        expected_host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
        if identity.get("normalized_host_sha256") != expected_host_hash:
            errors.append(f"Host hash mismatch: {row.get('candidate_id')}")
        if row.get("queue_state") != "PROVENANCE_ENUMERATED_UNCAPTURED":
            errors.append(f"Unexpected queue state: {row.get('candidate_id')}")
        capture = row.get("capture_plan", {})
        review = row.get("review_state", {})
        safety = row.get("safety", {})
        if any(
            capture.get(field) is not False
            for field in (
                "live_candidate_domain_access_allowed",
                "availability_query_started",
                "artifact_capture_started",
                "raw_capture_overwrite_allowed",
            )
        ):
            errors.append(f"Capture gate opened: {row.get('candidate_id')}")
        if review.get("ground_truth_status") != "UNCERTAIN" or review.get("label_created") is not False:
            errors.append(f"Ground truth inferred during B2: {row.get('candidate_id')}")
        if review.get("training_eligible") != "NO" or review.get("model_scoring_eligible") != "NO":
            errors.append(f"Model gate opened: {row.get('candidate_id')}")
        if any(safety.get(field) is not False for field in ("live_domain_accessed", "wayback_queried", "artifact_captured", "model_scored")):
            errors.append(f"Safety evidence changed: {row.get('candidate_id')}")

    expected_counts = {
        (channel, "DEVELOPMENT"): 25 for channel in EXPECTED_CHANNELS
    } | {(channel, "EXTERNAL_HOLDOUT"): 10 for channel in EXPECTED_CHANNELS}
    if len(queue) != 70 or dict(counts) != expected_counts:
        errors.append("B2 exact 70-row channel/cohort contract failed")
    if len(set(ids)) != len(ids) or len(set(hosts)) != len(hosts) or len(set(entities)) != len(entities):
        errors.append("Candidate, host, or normalized entity is not globally disjoint")
    if not all(hosts) or not all(entities):
        errors.append("Blank normalized host or entity found")

    expected_report_counts = {
        channel: {"DEVELOPMENT": 25, "EXTERNAL_HOLDOUT": 10} for channel in EXPECTED_CHANNELS
    }
    if report.get("status") != "PASS_EXACT_70_PROVENANCE_QUEUE_CREATED_CAPTURE_CLOSED":
        errors.append("Unexpected B2 report status")
    if report.get("release_sha256") != sha256_file(config_path):
        errors.append("B2 report release hash mismatch")
    if report.get("total_records") != 70 or report.get("counts") != expected_report_counts:
        errors.append("B2 report aggregate mismatch")
    if report.get("selection", {}).get("unique_hosts") != 70 or report.get("selection", {}).get("unique_normalized_entities") != 70:
        errors.append("B2 report disjointness aggregate mismatch")
    if report.get("safety_contract") != {
        "network_operations": 0,
        "candidate_domain_access_operations": 0,
        "wayback_queries": 0,
        "captures": 0,
        "labels_created": 0,
        "model_operations": 0,
        "training_allowed": False,
    }:
        errors.append("B2 report safety contract changed")

    development_hosts = {hosts[index] for index, row in enumerate(queue) if row.get("cohort") == "DEVELOPMENT"}
    holdout_hosts = {hosts[index] for index, row in enumerate(queue) if row.get("cohort") == "EXTERNAL_HOLDOUT"}
    development_entities = {entities[index] for index, row in enumerate(queue) if row.get("cohort") == "DEVELOPMENT"}
    holdout_entities = {entities[index] for index, row in enumerate(queue) if row.get("cohort") == "EXTERNAL_HOLDOUT"}
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_QUEUE_INDEPENDENT_QA_V1",
        "status": "PASS_EXACT_70_QUEUE_REPRODUCED_CAPTURE_REMAINS_CLOSED" if not errors else "FAIL",
        "inputs": {
            "release_sha256": sha256_file(config_path),
            "queue_sha256": sha256_file(queue_path),
            "report_sha256": sha256_file(report_path),
        },
        "checks": {
            "records": len(queue),
            "development_records": sum(row.get("cohort") == "DEVELOPMENT" for row in queue),
            "external_holdout_records": sum(row.get("cohort") == "EXTERNAL_HOLDOUT" for row in queue),
            "unique_candidate_ids": len(set(ids)),
            "unique_hosts": len(set(hosts)),
            "unique_normalized_entities": len(set(entities)),
            "development_holdout_host_overlap": len(development_hosts & holdout_hosts),
            "development_holdout_entity_overlap": len(development_entities & holdout_entities),
            "membership_and_order_independently_reproduced": actual_identities == expected_identities,
            "network_operations": 0,
            "captures": 0,
            "labels_created": 0,
            "model_operations": 0,
        },
        "decision": {
            "b2_complete": not errors,
            "b3_offline_wayback_availability_release_may_be_prepared": not errors,
            "network_access_allowed": False,
            "artifact_capture_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    release = load_object(args.config)
    queue_path = args.queue or Path(release["outputs"]["queue_path"])
    report_path = args.report or Path(release["outputs"]["report_path"])
    result = verify(args.config, queue_path, report_path)
    if result["status"] == "FAIL":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    if args.output:
        if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
            raise FileExistsError(f"Refusing to overwrite B2 independent QA: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
