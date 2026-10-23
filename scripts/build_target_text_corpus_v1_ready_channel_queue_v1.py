"""Build B2's exact two-channel development/holdout provenance queue offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_ready_channel_enumeration_release_v1 import verify as verify_b1
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.curation.target_text_candidate_enumeration import CHANNELS, _normalized_entity, _validate_reference_record


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def stable_key(seed: str, namespace: str, channel_id: str, row: dict[str, Any]) -> str:
    payload = "|".join((seed, namespace, channel_id, str(row["source_id"]), str(row["source_record_id"]), str(row["normalized_host"])))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_and_filter(b1: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    exclusions = {item["role"]: Path(item["path"]) for item in b1["exclusion_inputs"]}
    pilot = read_jsonl(exclusions["prior_four_channel_pilot_queue"])
    prior_sec = read_jsonl(exclusions["prior_sec_iapd_availability_population"])
    prior_hosts = {str(row["candidate_identity"]["normalized_host"]).casefold().rstrip(".") for row in pilot}
    prior_hosts.update(str(row["candidate_host"]).casefold().rstrip(".") for row in prior_sec)
    opened = load_object(exclusions["opened_external_exclusion_index"])
    opened_hashes = {str(row["normalized_host_sha256"]) for row in opened["records"]}

    kept: dict[str, list[dict[str, Any]]] = {}
    excluded: dict[str, Counter[str]] = {}
    targets = {item["channel_id"]: item["target_status"] for item in b1["channels"]}
    for item in b1["channels"]:
        channel = item["channel_id"]
        rows = read_jsonl(Path(item["pool_path"]))
        seen_hosts: set[str] = set()
        seen_refs: set[tuple[str, str]] = set()
        counter: Counter[str] = Counter()
        output: list[dict[str, Any]] = []
        for row in rows:
            errors = _validate_reference_record(channel, row)
            if errors:
                counter.update(errors)
                continue
            host = str(row["normalized_host"]).casefold().rstrip(".")
            ref = (str(row["source_id"]), str(row["source_record_id"]))
            if host in prior_hosts or hashlib.sha256(host.encode("utf-8")).hexdigest() in opened_hashes:
                counter["prior_opened_or_enumerated_host"] += 1
                continue
            if host in seen_hosts or ref in seen_refs:
                counter["duplicate_within_channel"] += 1
                continue
            seen_hosts.add(host)
            seen_refs.add(ref)
            normalized = dict(row)
            normalized["normalized_host"] = host
            normalized["normalized_entity"] = _normalized_entity(row["entity_name_from_reference"])
            output.append(normalized)
        kept[channel] = output
        excluded[channel] = counter

    host_channels: defaultdict[str, set[str]] = defaultdict(set)
    entity_strata: defaultdict[str, set[str]] = defaultdict(set)
    for channel, rows in kept.items():
        for row in rows:
            host_channels[row["normalized_host"]].add(channel)
            if row["normalized_entity"]:
                entity_strata[row["normalized_entity"]].add(targets[channel])
    cross_hosts = {host for host, values in host_channels.items() if len(values) > 1}
    cross_entities = {entity for entity, values in entity_strata.items() if len(values) > 1}
    for channel, rows in kept.items():
        filtered = []
        for row in rows:
            if row["normalized_host"] in cross_hosts:
                excluded[channel]["cross_channel_host_overlap"] += 1
                continue
            if row["normalized_entity"] in cross_entities:
                excluded[channel]["cross_stratum_entity_overlap"] += 1
                continue
            filtered.append(row)
        kept[channel] = filtered
    audit = {"prior_host_count": len(prior_hosts), "opened_host_hash_count": len(opened_hashes), "cross_channel_host_overlap_count": len(cross_hosts), "cross_stratum_entity_overlap_count": len(cross_entities), "exclusion_counts": {channel: dict(sorted(values.items())) for channel, values in excluded.items()}}
    return kept, audit


def candidate_record(channel: str, cohort: str, rank: int, row: dict[str, Any], enumerated_at: str) -> dict[str, Any]:
    prefix = "CONF_REG" if channel == "CONFIRMED_REGULATOR_LINKED_WEBSITE" else "LEGIT_IAPD"
    cohort_short = "DEV" if cohort == "DEVELOPMENT" else "HOLDOUT"
    host = row["normalized_host"]
    return {
        "schema_version": "target_text_candidate_v1_ready_channel_b2",
        "candidate_id": f"TTCV1_B2_{prefix}_{cohort_short}_{rank:03d}",
        "enumeration_wave_id": "TTCV1_READY_CHANNEL_B2_V1",
        "cohort": cohort,
        "channel_id": channel,
        "channel_target_stratum": CHANNELS[channel]["stratum"],
        "predicted_artifact_type": "WEBSITE_SNAPSHOT",
        "reference": {"source_id": row["source_id"], "source_record_id": str(row["source_record_id"]), "source_url": row["reference_url"], "reference_role": CHANNELS[channel]["reference_role"], "reference_observed_at": row["reference_observed_at"], "reference_sha256": row["reference_sha256"]},
        "candidate_identity": {"entity_name_from_reference": row["entity_name_from_reference"], "normalized_entity": row["normalized_entity"], "candidate_url": row["candidate_url"], "normalized_host": host, "normalized_host_sha256": hashlib.sha256(host.encode("utf-8")).hexdigest(), "identity_linkage_basis": row["identity_linkage_basis"]},
        "enumerated_at": enumerated_at,
        "queue_state": "PROVENANCE_ENUMERATED_UNCAPTURED",
        "exclusion_screen": {"prior_opened_or_enumerated_host": "PASS", "cross_channel_host": "PASS", "cross_stratum_entity": "PASS", "cross_cohort_host": "PASS", "cross_cohort_entity": "PASS", "exact_capture": "PENDING_CAPTURE", "exact_text": "PENDING_CAPTURE", "near_duplicate": "PENDING_CAPTURE"},
        "capture_plan": {"capture_source": "WAYBACK_MACHINE", "live_candidate_domain_access_allowed": False, "availability_query_started": False, "artifact_capture_started": False, "raw_capture_overwrite_allowed": False},
        "review_state": {"ground_truth_status": "UNCERTAIN", "label_created": False, "review_status": "UNREVIEWED", "primary_review": "NOT_STARTED", "independent_second_review": "NOT_STARTED", "owner_acceptance": "NOT_REQUESTED", "training_eligible": "NO", "model_scoring_eligible": "NO"},
        "safety": {"live_domain_accessed": False, "wayback_queried": False, "artifact_captured": False, "model_scored": False}
    }


def build(config_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    release = load_object(config_path)
    if release.get("release_id") != "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_QUEUE_RELEASE_V1":
        raise ValueError("Unexpected B2 queue release")
    root = config_path.resolve().parents[1]
    inputs = {item["role"]: item for item in release["inputs"]}
    for item in inputs.values():
        path = resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"B2 input mismatch: {item['role']}")
    b1_path = resolved(root, inputs["b1_release"]["path"])
    b1_preflight = verify_b1(b1_path)
    if b1_preflight["status"] != "PASS_TWO_READY_CHANNELS_CAPACITY_SUFFICIENT_QUEUE_MAY_BE_MATERIALIZED":
        raise PermissionError("B1 preflight no longer passes")
    for gate in ("network_access_allowed", "candidate_domain_access_allowed", "wayback_query_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if release["decision"].get(gate) is not False:
            raise PermissionError(f"B2 release opened forbidden gate: {gate}")
    b1 = load_object(b1_path)
    eligible, audit = load_and_filter(b1)
    contract = release["population_contract"]
    wave = b1["wave_contract"]
    selected: list[dict[str, Any]] = []
    selected_hosts: set[str] = set()
    selected_entities: set[str] = set()
    counts: Counter[tuple[str, str]] = Counter()
    for cohort, namespace, quota in (
        ("DEVELOPMENT", wave["development_namespace"], contract["development_per_channel"]),
        ("EXTERNAL_HOLDOUT", wave["external_holdout_namespace"], contract["external_holdout_per_channel"]),
    ):
        for channel in contract["channels"]:
            ranked = sorted(eligible[channel], key=lambda row: stable_key(wave["selection_seed"], namespace, channel, row))
            chosen = []
            cohort_entities: set[str] = set()
            for row in ranked:
                host = row["normalized_host"]
                entity = row["normalized_entity"]
                if host in selected_hosts or entity in selected_entities or entity in cohort_entities:
                    continue
                chosen.append(row)
                cohort_entities.add(entity)
                if len(chosen) == quota:
                    break
            if len(chosen) != quota:
                raise ValueError(f"B2 selection shortfall: {cohort}/{channel}")
            for rank, row in enumerate(chosen, 1):
                selected.append(candidate_record(channel, cohort, rank, row, contract["enumerated_at"]))
                selected_hosts.add(row["normalized_host"])
                selected_entities.add(row["normalized_entity"])
                counts[(channel, cohort)] += 1
    if len(selected) != contract["total_records"]:
        raise ValueError("B2 queue total mismatch")
    report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_ENUMERATION_REPORT_V1",
        "status": "PASS_EXACT_70_PROVENANCE_QUEUE_CREATED_CAPTURE_CLOSED",
        "release_sha256": sha256_file(config_path),
        "counts": {channel: {cohort: counts[(channel, cohort)] for cohort in ("DEVELOPMENT", "EXTERNAL_HOLDOUT")} for channel in contract["channels"]},
        "total_records": len(selected),
        "selection": {"seed": wave["selection_seed"], "development_namespace": wave["development_namespace"], "external_holdout_namespace": wave["external_holdout_namespace"], "unique_hosts": len(selected_hosts), "unique_normalized_entities": len(selected_entities)},
        "exclusion_audit": audit,
        "decision": {"queue_created": True, "independent_queue_qa_required": True, "wayback_availability_planning_allowed": False, "capture_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "wayback_queries": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    }
    return selected, report


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    queue, report = build(args.config)
    if args.verify_only:
        print(json.dumps({"status": report["status"], "total_records": len(queue), "counts": report["counts"], "decision": report["decision"]}, indent=2))
        return 0
    outputs = load_object(args.config)["outputs"]
    queue_path = Path(outputs["queue_path"])
    report_path = Path(outputs["report_path"])
    for path in (queue_path, report_path, queue_path.with_suffix(queue_path.suffix + ".partial"), report_path.with_suffix(report_path.suffix + ".partial")):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite B2 output: {path}")
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_partial = queue_path.with_suffix(queue_path.suffix + ".partial")
    report_partial = report_path.with_suffix(report_path.suffix + ".partial")
    write_jsonl(queue_partial, queue)
    report_partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    queue_partial.replace(queue_path)
    report_partial.replace(report_path)
    print(json.dumps({"status": report["status"], "queue_sha256": sha256_file(queue_path), "report_sha256": sha256_file(report_path), "records": len(queue)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
