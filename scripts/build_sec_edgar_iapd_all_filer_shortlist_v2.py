"""Build a bounded disjoint EDGAR/IAPD review shortlist from the verified pool."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.normalization.external_references import canonicalize_host


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def nested_value(row: dict[str, Any], field: str) -> Any:
    value: Any = row
    for part in field.split("."):
        value = value[part]
    return value


def require_host(value: Any) -> str:
    host = canonicalize_host(str(value or ""))
    if not host:
        raise ValueError("EDGAR shortlist source contains an invalid host or URL")
    return host


def selection_key(seed: str, namespace: str, channel: str, row: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{seed}|{namespace}|{channel}|{row['cik']}|{row['iapd_source_record_id']}|{row['normalized_host_sha256']}".encode()
    ).hexdigest()


def build(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("release_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_SHORTLIST_RELEASE_V2":
        raise ValueError("Unexpected EDGAR shortlist release identity")
    for item in config["basis"]:
        path = config_path.resolve().parents[1] / item["path"]
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"EDGAR shortlist basis mismatch: {item['role']}")
    for item in config["inputs"].values():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("EDGAR shortlist input hash mismatch")
    for item in config["prior_host_sources"]:
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("EDGAR shortlist prior-host source hash mismatch")
    decision = config["decision"]
    if not decision.get("bounded_shortlist_enumeration_allowed") or not decision.get("raw_host_release_for_selected_rows_allowed"):
        raise PermissionError("EDGAR bounded shortlist release is closed")
    for gate in ("candidate_live_domain_access_allowed", "wayback_query_allowed", "artifact_capture_allowed", "labeling_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            raise PermissionError(f"EDGAR shortlist opened forbidden gate: {gate}")
    outputs = {key: Path(value) for key, value in config["outputs"].items()}
    if any(path.exists() or path.with_suffix(path.suffix + ".partial").exists() for path in outputs.values()):
        raise FileExistsError("Refusing to overwrite EDGAR shortlist output")

    excluded: set[str] = set()
    source_counts: list[dict[str, Any]] = []
    for item in config["prior_host_sources"]:
        rows = load_jsonl(Path(item["path"]))
        if len(rows) != item["record_count"]:
            raise ValueError("EDGAR prior-host source row count mismatch")
        hashes = {
            hashlib.sha256(require_host(nested_value(row, item["host_field"])).encode()).hexdigest()
            for row in rows
        }
        excluded.update(hashes)
        source_counts.append({"path": item["path"], "rows": len(rows), "unique_host_hashes": len(hashes)})
    opened = load_object(Path(config["inputs"]["opened_exclusion_index"]["path"]))
    opened_hashes = {row["normalized_host_sha256"] for row in opened["records"]}
    excluded.update(opened_hashes)
    if len(excluded) != config["preflight"]["unique_excluded_host_hashes"]:
        raise ValueError("EDGAR shortlist exclusion-union count differs from preflight")

    pool = load_jsonl(Path(config["inputs"]["hashed_crosswalk_pool"]["path"]))
    eligible = [row for row in pool if row["normalized_host_sha256"] not in excluded]
    overlap = len(pool) - len(eligible)
    if overlap != config["preflight"]["crosswalk_rows_overlapping_exclusions"] or len(eligible) != config["preflight"]["eligible_crosswalk_rows"]:
        raise ValueError("EDGAR shortlist eligible-pool counts differ from preflight")
    selection = config["selection"]
    seed = selection["seed"]
    channel = selection["channel_id"]
    dev_namespace = selection["development_namespace"]
    hold_namespace = selection["external_holdout_namespace"]
    dev_ordered = sorted(eligible, key=lambda row: selection_key(seed, dev_namespace, channel, row))
    development = dev_ordered[: selection["development_size"]]
    development_ids = {(row["cik"], row["iapd_source_record_id"]) for row in development}
    remaining = [row for row in eligible if (row["cik"], row["iapd_source_record_id"]) not in development_ids]
    holdout = sorted(remaining, key=lambda row: selection_key(seed, hold_namespace, channel, row))[: selection["external_holdout_size"]]
    if len(development) + len(holdout) != selection["total_shortlist_size"]:
        raise ValueError("EDGAR shortlist is incomplete")

    iapd = load_jsonl(Path(config["inputs"]["iapd_normalized"]["path"]))
    iapd_by_id = {str(row["source_record_id"]): row for row in iapd}
    shortlist: list[dict[str, Any]] = []
    for cohort, namespace, rows, prefix in (
        ("DEVELOPMENT", dev_namespace, development, "TTCV1_EDGAR_DEV"),
        ("EXTERNAL_HOLDOUT", hold_namespace, holdout, "TTCV1_EDGAR_HOLDOUT"),
    ):
        ordered = sorted(rows, key=lambda row: selection_key(seed, namespace, channel, row))
        for rank, row in enumerate(ordered, start=1):
            source = iapd_by_id.get(row["iapd_source_record_id"])
            if source is None or source["entity_name_from_reference"] != row["iapd_entity_name"]:
                raise ValueError("EDGAR shortlist IAPD identity join mismatch")
            host = require_host(source["normalized_host"])
            host_hash = hashlib.sha256(host.encode()).hexdigest()
            if host_hash != row["normalized_host_sha256"] or require_host(source["candidate_url"]) != host:
                raise ValueError("EDGAR shortlist IAPD host or candidate URL mismatch")
            shortlist.append(
                {
                    "shortlist_id": f"{prefix}_{rank:03d}",
                    "cohort": cohort,
                    "acquisition_wave_id": namespace,
                    "channel_id": channel,
                    "source_id": "sec_edgar_company_submissions",
                    "cik": row["cik"],
                    "edgar_entity_name": row["edgar_entity_name"],
                    "iapd_source_record_id": row["iapd_source_record_id"],
                    "iapd_entity_name": row["iapd_entity_name"],
                    "normalized_host": host,
                    "normalized_host_sha256": host_hash,
                    "candidate_url": source["candidate_url"],
                    "name_token_jaccard": row["name_token_jaccard"],
                    "runner_up_margin": row["runner_up_margin"],
                    "selection_key": selection_key(seed, namespace, channel, row),
                    "identity_linkage_status": "PRELIMINARY_REVIEW_REQUIRED",
                    "ground_truth_status": "UNCERTAIN",
                    "candidate_live_domain_accessed": False,
                    "wayback_queried": False,
                    "artifact_captured": False,
                    "label_created": False,
                    "training_eligible": "NO",
                }
            )
    hashes = [row["normalized_host_sha256"] for row in shortlist]
    if len(hashes) != len(set(hashes)) or set(hashes) & excluded:
        raise ValueError("EDGAR shortlist is not host-disjoint")
    if {row["normalized_host_sha256"] for row in development} & {row["normalized_host_sha256"] for row in holdout}:
        raise ValueError("EDGAR development and holdout selections overlap")

    outputs["shortlist"].parent.mkdir(parents=True, exist_ok=True)
    shortlist_temp = outputs["shortlist"].with_suffix(outputs["shortlist"].suffix + ".partial")
    shortlist_temp.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in shortlist), encoding="utf-8")
    report = {
        "analysis_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_SHORTLIST_V2",
        "status": "FROZEN_BOUNDED_DISJOINT_REVIEW_SHORTLIST_CAPTURE_BLOCKED",
        "exclusions": {
            "prior_host_sources": source_counts,
            "opened_records": len(opened["records"]),
            "opened_unique_host_hashes": len(opened_hashes),
            "unique_excluded_host_hashes": len(excluded),
            "crosswalk_rows_excluded": overlap,
            "eligible_crosswalk_rows": len(eligible),
        },
        "output": {
            "shortlist_path": str(outputs["shortlist"]),
            "shortlist_sha256": sha256_file(shortlist_temp),
            "record_count": len(shortlist),
            "development_count": len(development),
            "external_holdout_count": len(holdout),
            "unique_host_count": len(set(hashes)),
            "prior_host_overlap_count": len(set(hashes) & excluded),
            "cross_cohort_host_overlap_count": 0,
        },
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "wayback_queries": 0,
            "artifact_captures": 0,
            "labels_created": 0,
            "training_allowed": False,
        },
    }
    report_temp = outputs["report"].with_suffix(outputs["report"].suffix + ".partial")
    report_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shortlist_temp.replace(outputs["shortlist"])
    report_temp.replace(outputs["report"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
