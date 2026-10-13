"""Independently verify the hashed all-filer EDGAR/IAPD crosswalk pool."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_crosswalk import tokens
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def insert_top_two(items: list[tuple[float, str]], score: float, cik: str) -> None:
    if any(existing_cik == cik for _, existing_cik in items):
        return
    items.append((score, cik))
    items.sort(key=lambda item: (-item[0], item[1]))
    del items[2:]


def verify(config_path: Path, output_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    pool_path = Path(config["outputs"]["pool"])
    report_path = Path(config["outputs"]["report"])
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite crosswalk verification output")
    report = load_object(report_path)
    if sha256_file(pool_path) != report["output"]["pool_sha256"]:
        raise ValueError("Crosswalk pool hash differs from materialization report")
    pool = [json.loads(line) for line in pool_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected_fields = {
        "cik", "edgar_entity_name", "iapd_source_record_id", "iapd_entity_name",
        "name_token_jaccard", "runner_up_score", "runner_up_margin",
        "shared_distinctive_tokens", "normalized_host_sha256", "selection_key",
        "identity_linkage_status", "ground_truth_status", "label_created",
    }
    if any(set(row) != expected_fields for row in pool):
        raise ValueError("Crosswalk pool schema changed or exposed a forbidden field")
    if len(pool) != config["method"]["expected_rows"]:
        raise ValueError("Crosswalk pool row count mismatch")
    if [row["selection_key"] for row in pool] != sorted(row["selection_key"] for row in pool):
        raise ValueError("Crosswalk pool ordering is not deterministic")
    if len({row["cik"] for row in pool}) != len(pool):
        raise ValueError("Crosswalk pool contains duplicate CIKs")
    if len({row["normalized_host_sha256"] for row in pool}) != len(pool):
        raise ValueError("Crosswalk pool contains duplicate host hashes")

    iapd_path = Path(config["inputs"]["iapd_normalized"]["path"])
    iapd_rows = [json.loads(line) for line in iapd_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    iapd_by_id = {str(row["source_record_id"]): row for row in iapd_rows}
    selected_tokens: list[set[str]] = []
    raw_triples: list[str] = []
    inverted: defaultdict[str, set[int]] = defaultdict(set)
    for index, row in enumerate(pool):
        source = iapd_by_id.get(row["iapd_source_record_id"])
        if source is None or source["entity_name_from_reference"] != row["iapd_entity_name"]:
            raise ValueError("Crosswalk pool IAPD identity mismatch")
        host = source["normalized_host"]
        host_hash = hashlib.sha256(host.encode()).hexdigest()
        if host_hash != row["normalized_host_sha256"]:
            raise ValueError("Crosswalk pool host hash mismatch")
        expected_key = hashlib.sha256(
            f"{config['method']['selection_seed']}|{row['cik']}|{row['iapd_source_record_id']}|{host_hash}".encode()
        ).hexdigest()
        if expected_key != row["selection_key"]:
            raise ValueError("Crosswalk pool selection key mismatch")
        raw_triples.append(f"{row['cik']}|{row['iapd_source_record_id']}|{host}")
        current = tokens(row["iapd_entity_name"])
        selected_tokens.append(current)
        for token in current:
            inverted[token].add(index)
    raw_fingerprint = hashlib.sha256("\n".join(sorted(raw_triples)).encode()).hexdigest()
    if raw_fingerprint != config["method"]["expected_raw_set_fingerprint"]:
        raise ValueError("Crosswalk pool raw-set fingerprint mismatch")

    top_two: list[list[tuple[float, str]]] = [[] for _ in pool]
    selected_cik_names: dict[str, str] = {}
    selected_ciks = {row["cik"] for row in pool}
    edgar_count = 0
    with Path(config["inputs"]["edgar_identity_index"]["path"]).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            edgar = json.loads(line)
            edgar_count += 1
            if edgar["cik"] in selected_ciks:
                selected_cik_names[edgar["cik"]] = edgar["name"]
            right = tokens(edgar["name"])
            candidates: set[int] = set()
            for token in right:
                candidates.update(inverted.get(token, ()))
            for index in candidates:
                left = selected_tokens[index]
                score = len(left & right) / len(left | right) if left | right else 0.0
                insert_top_two(top_two[index], score, edgar["cik"])
    if edgar_count != config["inputs"]["edgar_identity_index"]["record_count"]:
        raise ValueError("Verifier EDGAR row count mismatch")

    for index, row in enumerate(pool):
        if selected_cik_names.get(row["cik"]) != row["edgar_entity_name"]:
            raise ValueError("Crosswalk pool EDGAR identity mismatch")
        if len(top_two[index]) < 1 or top_two[index][0][1] != row["cik"]:
            raise ValueError("Crosswalk selected CIK is not the independently recomputed best match")
        best_score = top_two[index][0][0]
        runner_score = top_two[index][1][0] if len(top_two[index]) > 1 else 0.0
        if round(best_score, 6) != row["name_token_jaccard"]:
            raise ValueError("Crosswalk best score mismatch")
        if round(runner_score, 6) != row["runner_up_score"]:
            raise ValueError("Crosswalk runner-up score mismatch")
        if round(best_score - runner_score, 6) != row["runner_up_margin"]:
            raise ValueError("Crosswalk runner-up margin mismatch")
        if row["name_token_jaccard"] < 0.8 or row["runner_up_margin"] < 0.15:
            raise ValueError("Crosswalk row falls below frozen thresholds")
        if row["label_created"] is not False or row["ground_truth_status"] != "UNCERTAIN":
            raise ValueError("Crosswalk pool silently created a label")

    result = {
        "analysis_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_CROSSWALK_V2_INDEPENDENT_VERIFICATION",
        "status": "PASS_INDEPENDENT_REPRODUCTION_HASHED_IDENTITY_POOL_ONLY",
        "pool_sha256": sha256_file(pool_path),
        "record_count": len(pool),
        "unique_cik_count": len({row["cik"] for row in pool}),
        "unique_host_hash_count": len({row["normalized_host_sha256"] for row in pool}),
        "raw_set_fingerprint": raw_fingerprint,
        "independently_recomputed_best_and_runner_up_rows": len(pool),
        "raw_hosts_or_candidate_urls_emitted_by_pool": 0,
        "candidate_enumeration_allowed": False,
        "labels_created": 0,
        "training_allowed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".partial")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.config, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
