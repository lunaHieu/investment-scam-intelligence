"""Independently verify the bounded disjoint EDGAR/IAPD shortlist release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.normalization.external_references import canonicalize_host


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dotted_value(row: dict[str, Any], field: str) -> Any:
    value: Any = row
    for component in field.split("."):
        value = value[component]
    return value


def canonical_host(value: Any) -> str:
    host = canonicalize_host(str(value or ""))
    if not host:
        raise ValueError("Independent shortlist verification found an invalid host or URL")
    return host


def rank_digest(seed: str, namespace: str, channel: str, row: dict[str, Any]) -> str:
    material = "|".join(
        (seed, namespace, channel, str(row["cik"]), str(row["iapd_source_record_id"]), row["normalized_host_sha256"])
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def verify(config_path: Path, output_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("release_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_SHORTLIST_RELEASE_V2":
        raise ValueError("Unexpected EDGAR shortlist release identity")

    repo_root = config_path.resolve().parents[1]
    for item in config["basis"]:
        if sha256_file(repo_root / item["path"]) != item["sha256"]:
            raise ValueError(f"Independent shortlist basis hash mismatch: {item['role']}")
    for item in config["inputs"].values():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("Independent shortlist input hash mismatch")

    excluded: set[str] = set()
    exclusion_rows = 0
    for item in config["prior_host_sources"]:
        source_path = Path(item["path"])
        if sha256_file(source_path) != item["sha256"]:
            raise ValueError("Independent prior-host source hash mismatch")
        rows = read_jsonl(source_path)
        if len(rows) != item["record_count"]:
            raise ValueError("Independent prior-host source count mismatch")
        exclusion_rows += len(rows)
        for row in rows:
            host = canonical_host(dotted_value(row, item["host_field"]))
            excluded.add(hashlib.sha256(host.encode("utf-8")).hexdigest())

    opened = load_object(Path(config["inputs"]["opened_exclusion_index"]["path"]))
    opened_hashes = {row["normalized_host_sha256"] for row in opened["records"]}
    excluded.update(opened_hashes)
    if len(excluded) != config["preflight"]["unique_excluded_host_hashes"]:
        raise ValueError("Independent exclusion-union reproduction failed")

    pool = read_jsonl(Path(config["inputs"]["hashed_crosswalk_pool"]["path"]))
    if len(pool) != config["inputs"]["hashed_crosswalk_pool"]["record_count"]:
        raise ValueError("Independent hashed-pool count mismatch")
    eligible = [row for row in pool if row["normalized_host_sha256"] not in excluded]
    if len(pool) - len(eligible) != config["preflight"]["crosswalk_rows_overlapping_exclusions"]:
        raise ValueError("Independent excluded-pool overlap mismatch")
    if len(eligible) != config["preflight"]["eligible_crosswalk_rows"]:
        raise ValueError("Independent eligible-pool count mismatch")

    selection = config["selection"]
    seed = selection["seed"]
    channel = selection["channel_id"]
    dev_namespace = selection["development_namespace"]
    hold_namespace = selection["external_holdout_namespace"]
    expected_dev = sorted(eligible, key=lambda row: rank_digest(seed, dev_namespace, channel, row))[: selection["development_size"]]
    dev_pairs = {(row["cik"], row["iapd_source_record_id"]) for row in expected_dev}
    remaining = [row for row in eligible if (row["cik"], row["iapd_source_record_id"]) not in dev_pairs]
    expected_holdout = sorted(remaining, key=lambda row: rank_digest(seed, hold_namespace, channel, row))[: selection["external_holdout_size"]]

    shortlist_path = Path(config["outputs"]["shortlist"])
    shortlist = read_jsonl(shortlist_path)
    if len(shortlist) != selection["total_shortlist_size"]:
        raise ValueError("Independent shortlist total count mismatch")
    expected_fields = {
        "shortlist_id", "cohort", "acquisition_wave_id", "channel_id", "source_id", "cik", "edgar_entity_name",
        "iapd_source_record_id", "iapd_entity_name", "normalized_host", "normalized_host_sha256", "candidate_url",
        "name_token_jaccard", "runner_up_margin", "selection_key", "identity_linkage_status", "ground_truth_status",
        "candidate_live_domain_accessed", "wayback_queried", "artifact_captured", "label_created", "training_eligible",
    }
    if any(set(row) != expected_fields for row in shortlist):
        raise ValueError("Independent shortlist schema check failed")

    dev_actual = [row for row in shortlist if row["cohort"] == "DEVELOPMENT"]
    hold_actual = [row for row in shortlist if row["cohort"] == "EXTERNAL_HOLDOUT"]
    if len(dev_actual) != selection["development_size"] or len(hold_actual) != selection["external_holdout_size"]:
        raise ValueError("Independent shortlist cohort counts mismatch")
    if len({row["shortlist_id"] for row in shortlist}) != len(shortlist):
        raise ValueError("Independent shortlist ID uniqueness failed")
    if len({row["normalized_host_sha256"] for row in shortlist}) != len(shortlist):
        raise ValueError("Independent shortlist host uniqueness failed")
    if {row["normalized_host_sha256"] for row in shortlist} & excluded:
        raise ValueError("Independent shortlist prior-host disjointness failed")
    if {row["normalized_host_sha256"] for row in dev_actual} & {row["normalized_host_sha256"] for row in hold_actual}:
        raise ValueError("Independent shortlist cohort disjointness failed")

    iapd_rows = read_jsonl(Path(config["inputs"]["iapd_normalized"]["path"]))
    iapd_by_id = {str(row["source_record_id"]): row for row in iapd_rows}
    pool_by_pair = {(row["cik"], row["iapd_source_record_id"]): row for row in pool}
    expected_groups = ((dev_actual, expected_dev, dev_namespace, "TTCV1_EDGAR_DEV"), (hold_actual, expected_holdout, hold_namespace, "TTCV1_EDGAR_HOLDOUT"))
    for actual_rows, expected_rows, namespace, prefix in expected_groups:
        ordered_expected = sorted(expected_rows, key=lambda row: rank_digest(seed, namespace, channel, row))
        if [(row["cik"], row["iapd_source_record_id"]) for row in actual_rows] != [
            (row["cik"], row["iapd_source_record_id"]) for row in ordered_expected
        ]:
            raise ValueError("Independent deterministic shortlist reproduction failed")
        for rank, (actual, expected) in enumerate(zip(actual_rows, ordered_expected), start=1):
            source = iapd_by_id.get(str(actual["iapd_source_record_id"]))
            pool_row = pool_by_pair.get((actual["cik"], actual["iapd_source_record_id"]))
            if source is None or pool_row != expected:
                raise ValueError("Independent shortlist source join failed")
            host = canonical_host(source["candidate_url"])
            expected_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
            if canonical_host(source["normalized_host"]) != host or actual["normalized_host"] != host or actual["normalized_host_sha256"] != expected_hash:
                raise ValueError("Independent shortlist host provenance failed")
            if actual["shortlist_id"] != f"{prefix}_{rank:03d}" or actual["selection_key"] != rank_digest(seed, namespace, channel, expected):
                raise ValueError("Independent shortlist rank identity failed")
            if actual["edgar_entity_name"] != expected["edgar_entity_name"] or actual["iapd_entity_name"] != source["entity_name_from_reference"]:
                raise ValueError("Independent shortlist entity identity failed")
            if actual["acquisition_wave_id"] != namespace or actual["channel_id"] != channel:
                raise ValueError("Independent shortlist namespace check failed")
            if actual["identity_linkage_status"] != "PRELIMINARY_REVIEW_REQUIRED" or actual["ground_truth_status"] != "UNCERTAIN":
                raise ValueError("Independent shortlist review-state check failed")
            if any(actual[field] is not False for field in ("candidate_live_domain_accessed", "wayback_queried", "artifact_captured", "label_created")):
                raise ValueError("Independent shortlist closed-gate check failed")
            if actual["training_eligible"] != "NO":
                raise ValueError("Independent shortlist training gate opened")

    report_path = Path(config["outputs"]["report"])
    report = load_object(report_path)
    if report["output"]["shortlist_sha256"] != sha256_file(shortlist_path):
        raise ValueError("Independent shortlist report hash mismatch")
    if report["output"]["record_count"] != len(shortlist) or report["output"]["prior_host_overlap_count"] != 0:
        raise ValueError("Independent shortlist report findings mismatch")

    verification = {
        "verification_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_SHORTLIST_INDEPENDENT_VERIFICATION_V2",
        "status": "PASS",
        "config_sha256": sha256_file(config_path),
        "shortlist_sha256": sha256_file(shortlist_path),
        "report_sha256": sha256_file(report_path),
        "reproduced_counts": {
            "prior_source_rows": exclusion_rows,
            "opened_records": len(opened["records"]),
            "unique_excluded_host_hashes": len(excluded),
            "eligible_pool_rows": len(eligible),
            "shortlist_rows": len(shortlist),
            "development_rows": len(dev_actual),
            "external_holdout_rows": len(hold_actual),
        },
        "checks": {
            "all_pinned_inputs_match": True,
            "deterministic_selection_exactly_reproduced": True,
            "prior_host_overlap_count": 0,
            "cross_cohort_host_overlap_count": 0,
            "raw_host_and_candidate_url_provenance_verified": True,
            "closed_safety_gates_verified": True,
        },
        "operations": {"network": 0, "candidate_domain_access": 0, "wayback_queries": 0, "captures": 0, "labels": 0, "model": 0},
    }
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite independent shortlist verification")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".partial")
    temporary.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return verification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.config, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
