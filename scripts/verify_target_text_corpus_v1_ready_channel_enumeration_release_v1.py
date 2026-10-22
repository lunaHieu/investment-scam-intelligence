"""Verify B1 ready-channel capacity after every frozen identity exclusion."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.curation.target_text_candidate_enumeration import _normalized_entity, _validate_reference_record


EXPECTED_CHANNELS = {"CONFIRMED_REGULATOR_LINKED_WEBSITE", "LEGITIMATE_REGISTER_LINKED_WEBSITE"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def verify(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("release_id") != "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_ENUMERATION_RELEASE_V1":
        raise ValueError("Unexpected ready-channel release")
    root = config_path.resolve().parents[1]
    for item in config["basis"]:
        path = resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Release basis mismatch: {item['role']}")
    exclusion_paths: dict[str, Path] = {}
    for item in config["exclusion_inputs"]:
        path = resolved(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Exclusion input mismatch: {item['role']}")
        exclusion_paths[item["role"]] = path
    channels = {item["channel_id"]: item for item in config["channels"]}
    if set(channels) != EXPECTED_CHANNELS:
        raise ValueError("B1 must contain exactly the two capacity-ready channels")
    wave = config["wave_contract"]
    if wave["development_namespace"] == wave["external_holdout_namespace"] or wave["total_planned_candidates"] != 70:
        raise ValueError("Cohort namespace or quota contract changed")
    for gate in ("network_access_allowed", "candidate_domain_access_allowed", "wayback_query_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if config["decision"].get(gate) is not False:
            raise PermissionError(f"B1 release opened forbidden gate: {gate}")

    pilot_rows = read_jsonl(exclusion_paths["prior_four_channel_pilot_queue"])
    sec_rows = read_jsonl(exclusion_paths["prior_sec_iapd_availability_population"])
    prior_hosts = {str(row["candidate_identity"]["normalized_host"]).casefold().rstrip(".") for row in pilot_rows}
    prior_hosts.update(str(row["candidate_host"]).casefold().rstrip(".") for row in sec_rows)
    opened = load_object(exclusion_paths["opened_external_exclusion_index"])
    opened_hashes = {str(row["normalized_host_sha256"]) for row in opened["records"]}

    eligible: dict[str, list[dict[str, Any]]] = {}
    exclusions: dict[str, Counter[str]] = {}
    for channel_id, item in channels.items():
        path = Path(item["pool_path"])
        if not path.is_file() or sha256_file(path) != item["pool_sha256"]:
            raise ValueError(f"Channel pool hash mismatch: {channel_id}")
        rows = read_jsonl(path)
        if len(rows) != item["expected_pool_rows"]:
            raise ValueError(f"Channel pool row count changed: {channel_id}")
        counter: Counter[str] = Counter()
        kept: list[dict[str, Any]] = []
        seen_hosts: set[str] = set()
        seen_refs: set[tuple[str, str]] = set()
        for row in rows:
            errors = _validate_reference_record(channel_id, row)
            if errors:
                counter.update(errors)
                continue
            host = str(row["normalized_host"]).casefold().rstrip(".")
            ref = (str(row["source_id"]), str(row["source_record_id"]))
            host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
            if host in prior_hosts or host_hash in opened_hashes:
                counter["prior_opened_or_enumerated_host"] += 1
                continue
            if host in seen_hosts or ref in seen_refs:
                counter["duplicate_within_channel"] += 1
                continue
            seen_hosts.add(host)
            seen_refs.add(ref)
            normalized = dict(row)
            normalized["normalized_host"] = host
            kept.append(normalized)
        eligible[channel_id] = kept
        exclusions[channel_id] = counter

    host_channels: defaultdict[str, set[str]] = defaultdict(set)
    entity_strata: defaultdict[str, set[str]] = defaultdict(set)
    targets = {item["channel_id"]: item["target_status"] for item in config["channels"]}
    for channel_id, rows in eligible.items():
        for row in rows:
            host_channels[row["normalized_host"]].add(channel_id)
            entity = _normalized_entity(row["entity_name_from_reference"])
            if entity:
                entity_strata[entity].add(targets[channel_id])
    cross_hosts = {host for host, memberships in host_channels.items() if len(memberships) > 1}
    cross_entities = {entity for entity, strata in entity_strata.items() if len(strata) > 1}
    final_counts: dict[str, int] = {}
    for channel_id, rows in eligible.items():
        final = []
        for row in rows:
            if row["normalized_host"] in cross_hosts:
                exclusions[channel_id]["cross_channel_host_overlap"] += 1
                continue
            if _normalized_entity(row["entity_name_from_reference"]) in cross_entities:
                exclusions[channel_id]["cross_stratum_entity_overlap"] += 1
                continue
            final.append(row)
        final_counts[channel_id] = len(final)
    required = wave["total_candidates_per_channel"]
    shortfalls = {channel: count for channel, count in final_counts.items() if count < required}
    if shortfalls:
        raise ValueError(f"Ready-channel capacity shortfall: {shortfalls}")
    return {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_ENUMERATION_PREFLIGHT_V1",
        "status": "PASS_TWO_READY_CHANNELS_CAPACITY_SUFFICIENT_QUEUE_MAY_BE_MATERIALIZED",
        "release_sha256": sha256_file(config_path),
        "checks": {
            "channel_count": len(channels),
            "eligible_after_all_exclusions": final_counts,
            "required_per_channel": required,
            "planned_development_per_channel": wave["development_candidates_per_channel"],
            "planned_external_holdout_per_channel": wave["external_holdout_candidates_per_channel"],
            "prior_host_count": len(prior_hosts),
            "opened_host_hash_count": len(opened_hashes),
            "cross_channel_host_overlap_count": len(cross_hosts),
            "cross_stratum_entity_overlap_count": len(cross_entities),
            "exclusion_counts": {channel: dict(sorted(values.items())) for channel, values in exclusions.items()}
        },
        "decision": {"b1_complete": True, "b2_queue_materialization_allowed": True, "candidate_queue_created": False, "capture_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "candidates_selected": 0, "artifacts_captured": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False}
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = verify(args.config)
    if args.verify_only:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        raise ValueError("--output is required unless --verify-only is used")
    expected = Path(load_object(args.config)["planned_output"]["preflight_path"])
    if args.output.resolve() != expected.resolve():
        raise ValueError("Output path differs from frozen release")
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite B1 preflight")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"status": result["status"], "output": str(args.output), "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
