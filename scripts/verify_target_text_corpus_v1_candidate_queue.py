"""Independently verify the frozen 40-record Target Text Corpus V1 candidate queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_target_text_corpus_v1_schema_review_pilot import validate_candidate


CHANNELS = (
    "CONFIRMED_REGULATOR_LINKED_WEBSITE",
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE",
    "LEGITIMATE_REGISTER_LINKED_WEBSITE",
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized_entity(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def stable_key(seed: str, channel: str, record: dict) -> str:
    value = "|".join(
        (
            seed,
            channel,
            str(record["source_id"]),
            str(record["source_record_id"]),
            str(record["normalized_host"]),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def independent_expected_selection(
    inputs: dict[str, list[dict]], seed: str, quota: int = 10
) -> dict[str, list[tuple[str, str, str]]]:
    eligible: dict[str, list[dict]] = {}
    for channel, rows in inputs.items():
        seen_refs: set[tuple[str, str]] = set()
        seen_hosts: set[str] = set()
        unique: list[dict] = []
        for row in rows:
            reference_key = (str(row["source_id"]), str(row["source_record_id"]))
            host = str(row["normalized_host"]).casefold().rstrip(".")
            if reference_key in seen_refs or host in seen_hosts:
                continue
            seen_refs.add(reference_key)
            seen_hosts.add(host)
            unique.append(row)
        eligible[channel] = unique
    host_channels: defaultdict[str, set[str]] = defaultdict(set)
    entity_strata: defaultdict[str, set[str]] = defaultdict(set)
    for channel, rows in eligible.items():
        stratum = "CONFIRMED" if channel.startswith("CONFIRMED_") else "LEGITIMATE"
        for row in rows:
            host_channels[row["normalized_host"]].add(channel)
            entity_strata[normalized_entity(row["entity_name_from_reference"])].add(stratum)
    collided_hosts = {host for host, channels in host_channels.items() if len(channels) > 1}
    collided_entities = {entity for entity, strata in entity_strata.items() if len(strata) > 1}
    output: dict[str, list[tuple[str, str, str]]] = {}
    for channel, rows in eligible.items():
        filtered = [
            row
            for row in rows
            if row["normalized_host"] not in collided_hosts
            and normalized_entity(row["entity_name_from_reference"]) not in collided_entities
        ]
        filtered.sort(key=lambda row: stable_key(seed, channel, row))
        output[channel] = [
            (str(row["source_id"]), str(row["source_record_id"]), row["normalized_host"])
            for row in filtered[:quota]
        ]
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--enumeration-report", type=Path, required=True)
    parser.add_argument("--pilot-protocol", type=Path, required=True)
    parser.add_argument("--opened-exclusion-index", type=Path, required=True)
    parser.add_argument("--confirmed-regulator", type=Path, required=True)
    parser.add_argument("--confirmed-cftc", type=Path, required=True)
    parser.add_argument("--legitimate-iapd", type=Path, required=True)
    parser.add_argument("--legitimate-edgar", type=Path, required=True)
    parser.add_argument("--iosco-index", type=Path, required=True)
    parser.add_argument("--iapd-index", type=Path, required=True)
    parser.add_argument("--cftc-detail-directory", type=Path, required=True)
    parser.add_argument("--edgar-submissions-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    queue = load_jsonl(args.queue)
    report = json.loads(args.enumeration_report.read_text(encoding="utf-8"))
    protocol = json.loads(args.pilot_protocol.read_text(encoding="utf-8"))
    exclusion = json.loads(args.opened_exclusion_index.read_text(encoding="utf-8"))
    inputs = {
        CHANNELS[0]: load_jsonl(args.confirmed_regulator),
        CHANNELS[1]: load_jsonl(args.confirmed_cftc),
        CHANNELS[2]: load_jsonl(args.legitimate_iapd),
        CHANNELS[3]: load_jsonl(args.legitimate_edgar),
    }
    errors: list[str] = []
    if len(queue) != 40:
        errors.append(f"Queue count is {len(queue)}, expected 40")
    candidate_errors = {
        row.get("candidate_id", f"row-{index}"): validate_candidate(row)
        for index, row in enumerate(queue)
        if validate_candidate(row)
    }
    if candidate_errors:
        errors.append(f"Candidate schema errors: {candidate_errors}")
    candidate_ids = [row["candidate_id"] for row in queue]
    hosts = [row["candidate_identity"]["normalized_host"] for row in queue]
    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append("Candidate IDs are not unique")
    if len(set(hosts)) != len(hosts):
        errors.append("Candidate hosts are not unique")
    opened_host_hashes = {
        row["normalized_host_sha256"]
        for row in exclusion.get("records", [])
        if row.get("normalized_host_sha256")
    }
    queue_host_hashes = {
        hashlib.sha256(host.encode("utf-8")).hexdigest() for host in hosts
    }
    if queue_host_hashes & opened_host_hashes:
        errors.append("Queue overlaps an opened-cohort host")
    counts: defaultdict[str, int] = defaultdict(int)
    selected: defaultdict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for row in queue:
        channel = row["channel_id"]
        counts[channel] += 1
        selected[channel].append(
            (
                row["reference"]["source_id"],
                row["reference"]["source_record_id"],
                row["candidate_identity"]["normalized_host"],
            )
        )
    if dict(counts) != {channel: 10 for channel in CHANNELS}:
        errors.append(f"Channel quotas changed: {dict(counts)}")
    expected = independent_expected_selection(
        inputs, protocol["selection_contract"]["selection_seed"], quota=10
    )
    for channel in CHANNELS:
        if selected[channel] != expected[channel]:
            errors.append(f"Independent deterministic selection mismatch: {channel}")
    input_lookup = {
        channel: {
            (str(row["source_id"]), str(row["source_record_id"]), row["normalized_host"]): row
            for row in rows
        }
        for channel, rows in inputs.items()
    }
    for row in queue:
        key = (
            row["reference"]["source_id"],
            row["reference"]["source_record_id"],
            row["candidate_identity"]["normalized_host"],
        )
        source = input_lookup[row["channel_id"]].get(key)
        if source is None or source["reference_sha256"] != row["reference"]["reference_sha256"]:
            errors.append(f"Queue/reference input mismatch: {row['candidate_id']}")
    iosco_hash = sha256_file(args.iosco_index)
    iapd_hash = sha256_file(args.iapd_index)
    for row in queue:
        source_id = row["reference"]["source_id"]
        expected_hash: str | None = None
        if source_id == "iosco_i_scan":
            expected_hash = iosco_hash
        elif source_id == "sec_iapd":
            expected_hash = iapd_hash
        elif source_id == "cftc_red_list":
            path = args.cftc_detail_directory / (
                f"detail_{row['reference']['source_record_id']}_2026-10-03.html"
            )
            expected_hash = sha256_file(path) if path.is_file() else None
        elif source_id == "sec_edgar_company_submissions":
            path = args.edgar_submissions_directory / (
                f"CIK{row['reference']['source_record_id']}.json"
            )
            expected_hash = sha256_file(path) if path.is_file() else None
        if expected_hash != row["reference"]["reference_sha256"]:
            errors.append(f"Reference artifact hash mismatch: {row['candidate_id']}")
    if report.get("selected_total") != 40 or report.get("selected_counts") != {
        channel: 10 for channel in CHANNELS
    }:
        errors.append("Enumeration report coverage mismatch")
    if report.get("readiness", {}).get("capture_allowed") is not False:
        errors.append("Enumeration report opened capture")
    qa = {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_CANDIDATE_QUEUE_INDEPENDENT_QA_V1",
        "status": "PASS_PROVENANCE_QUEUE_FROZEN_CAPTURE_BLOCKED" if not errors else "FAIL",
        "queue": {"path": str(args.queue), "sha256": sha256_file(args.queue), "record_count": len(queue)},
        "enumeration_report": {
            "path": str(args.enumeration_report),
            "sha256": sha256_file(args.enumeration_report),
        },
        "checks": {
            "candidate_schema_valid": not candidate_errors,
            "unique_candidate_ids": len(set(candidate_ids)) == len(candidate_ids),
            "unique_candidate_hosts": len(set(hosts)) == len(hosts),
            "opened_host_overlap_count": len(queue_host_hashes & opened_host_hashes),
            "deterministic_selection_independently_reproduced": not any(
                "deterministic selection mismatch" in error for error in errors
            ),
            "reference_artifact_hashes_verified": not any(
                "Reference artifact hash mismatch" in error for error in errors
            ),
            "channel_counts": dict(counts),
        },
        "decision": {
            "provenance_qa_passed": not errors,
            "queue_hash_registration_allowed": not errors,
            "candidate_capture_allowed": False,
            "binary_labeling_allowed": False,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
