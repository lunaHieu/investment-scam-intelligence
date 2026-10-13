"""Materialize a hashed EDGAR/IAPD all-filer identity review pool."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_crosswalk import tokens
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def better(score: float, cik: str, current: tuple[float, str, str]) -> bool:
    return score > current[0] or (score == current[0] and (not current[1] or cik < current[1]))


def materialize(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_CROSSWALK_MATERIALIZATION_V2":
        raise ValueError("Unexpected crosswalk materialization protocol")
    for item in config["basis"]:
        path = config_path.resolve().parents[1] / item["path"]
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Crosswalk materialization basis mismatch: {item['role']}")
    for item in config["inputs"].values():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("Crosswalk materialization input hash mismatch")
    decision = config["decision"]
    if decision.get("hashed_identity_review_pool_materialization_allowed") is not True:
        raise PermissionError("Hashed crosswalk materialization is closed")
    for gate in (
        "raw_host_release_allowed",
        "candidate_enumeration_allowed",
        "shortlist_materialization_allowed",
        "artifact_capture_allowed",
        "labeling_allowed",
        "training_allowed",
    ):
        if decision.get(gate) is not False:
            raise PermissionError(f"Crosswalk materialization opened forbidden gate: {gate}")
    outputs = {key: Path(value) for key, value in config["outputs"].items()}
    if any(path.exists() or path.with_suffix(path.suffix + ".partial").exists() for path in outputs.values()):
        raise FileExistsError("Refusing to overwrite crosswalk materialization output")

    iapd = load_jsonl(Path(config["inputs"]["iapd_normalized"]["path"]))
    iapd_tokens = [tokens(row["entity_name_from_reference"]) for row in iapd]
    inverted: defaultdict[str, set[int]] = defaultdict(set)
    for index, current in enumerate(iapd_tokens):
        for token in current:
            inverted[token].add(index)
    best = [(0.0, "", "") for _ in iapd]
    second = [(0.0, "", "") for _ in iapd]
    edgar_count = 0
    with Path(config["inputs"]["edgar_identity_index"]["path"]).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            edgar_count += 1
            current_tokens = tokens(row["name"])
            candidates: set[int] = set()
            for token in current_tokens:
                candidates.update(inverted.get(token, ()))
            for index in candidates:
                left = iapd_tokens[index]
                score = len(left & current_tokens) / len(left | current_tokens) if left | current_tokens else 0.0
                candidate = (score, row["cik"], row["name"])
                if better(score, row["cik"], best[index]):
                    if best[index][1] and best[index][1] != row["cik"]:
                        second[index] = best[index]
                    best[index] = candidate
                elif row["cik"] != best[index][1] and better(score, row["cik"], second[index]):
                    second[index] = candidate
    if edgar_count != config["inputs"]["edgar_identity_index"]["record_count"]:
        raise ValueError("EDGAR row count differs from materialization protocol")

    method = config["method"]
    qualified: list[dict[str, Any]] = []
    for index, row in enumerate(iapd):
        score, cik, edgar_name = best[index]
        margin = score - second[index][0]
        if score >= method["name_token_jaccard_minimum"] and margin >= method["runner_up_margin_minimum"]:
            qualified.append(
                {
                    "cik": cik,
                    "edgar_entity_name": edgar_name,
                    "iapd_source_record_id": str(row["source_record_id"]),
                    "iapd_entity_name": row["entity_name_from_reference"],
                    "raw_host": row["normalized_host"],
                    "name_token_jaccard": round(score, 6),
                    "runner_up_score": round(second[index][0], 6),
                    "runner_up_margin": round(margin, 6),
                    "shared_distinctive_tokens": sorted(iapd_tokens[index] & tokens(edgar_name)),
                }
            )
    by_cik: defaultdict[str, int] = defaultdict(int)
    by_host: defaultdict[str, int] = defaultdict(int)
    for row in qualified:
        by_cik[row["cik"]] += 1
        by_host[row["raw_host"]] += 1
    unique = [row for row in qualified if by_cik[row["cik"]] == 1 and by_host[row["raw_host"]] == 1]
    raw_fingerprint = hashlib.sha256(
        "\n".join(sorted(f"{row['cik']}|{row['iapd_source_record_id']}|{row['raw_host']}" for row in unique)).encode()
    ).hexdigest()
    if len(unique) != method["expected_rows"] or raw_fingerprint != method["expected_raw_set_fingerprint"]:
        raise ValueError("Materialized crosswalk set differs from frozen capacity audit")
    seed = method["selection_seed"]
    pool: list[dict[str, Any]] = []
    for row in unique:
        host_hash = hashlib.sha256(row.pop("raw_host").encode()).hexdigest()
        selection_key = hashlib.sha256(
            f"{seed}|{row['cik']}|{row['iapd_source_record_id']}|{host_hash}".encode()
        ).hexdigest()
        pool.append(
            {
                **row,
                "normalized_host_sha256": host_hash,
                "selection_key": selection_key,
                "identity_linkage_status": "PRELIMINARY_INDEPENDENT_REVIEW_REQUIRED",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
            }
        )
    pool.sort(key=lambda row: row["selection_key"])
    pool_fingerprint = hashlib.sha256(
        "\n".join(f"{row['cik']}|{row['iapd_source_record_id']}|{row['normalized_host_sha256']}" for row in pool).encode()
    ).hexdigest()
    outputs["pool"].parent.mkdir(parents=True, exist_ok=True)
    pool_temp = outputs["pool"].with_suffix(outputs["pool"].suffix + ".partial")
    pool_temp.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in pool), encoding="utf-8"
    )
    report = {
        "analysis_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_CROSSWALK_MATERIALIZATION_V2",
        "status": "FROZEN_HASHED_IDENTITY_REVIEW_POOL_INDEPENDENT_VERIFICATION_REQUIRED",
        "inputs": {"edgar_rows": edgar_count, "iapd_rows": len(iapd)},
        "thresholds": {
            "name_token_jaccard_minimum": method["name_token_jaccard_minimum"],
            "runner_up_margin_minimum": method["runner_up_margin_minimum"],
        },
        "output": {
            "pool_path": str(outputs["pool"]),
            "pool_sha256": sha256_file(pool_temp),
            "record_count": len(pool),
            "unique_cik_count": len({row["cik"] for row in pool}),
            "unique_host_hash_count": len({row["normalized_host_sha256"] for row in pool}),
            "raw_set_fingerprint": raw_fingerprint,
            "hashed_pool_fingerprint": pool_fingerprint,
            "raw_hosts_or_candidate_urls_emitted": 0,
        },
        "safety_contract": {
            "candidate_records_enumerated": 0,
            "labels_created": 0,
            "training_allowed": False,
        },
    }
    report_temp = outputs["report"].with_suffix(outputs["report"].suffix + ".partial")
    report_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pool_temp.replace(outputs["pool"])
    report_temp.replace(outputs["report"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
