"""Audit aggregate EDGAR/IAPD linkage capacity without emitting identity rows."""

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


def update_top_two(
    best: list[tuple[float, str]], second: list[tuple[float, str]], index: int, score: float, cik: str
) -> None:
    candidate = (score, cik)
    current = best[index]
    if score > current[0] or (score == current[0] and (not current[1] or cik < current[1])):
        if current[1] and current[1] != cik:
            second[index] = current
        best[index] = candidate
    elif cik != current[1]:
        runner = second[index]
        if score > runner[0] or (score == runner[0] and (not runner[1] or cik < runner[1])):
            second[index] = candidate


def audit(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("audit_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_CAPACITY_AUDIT_V1":
        raise ValueError("Unexpected all-filer capacity audit identity")
    for item in config["basis"]:
        path = config_path.resolve().parents[1] / item["path"]
        if sha256_file(path) != item["sha256"]:
            raise ValueError("All-filer capacity audit basis hash mismatch")
    for item in config["inputs"].values():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("All-filer capacity audit input hash mismatch")
    if config["decision"] != {
        "capacity_audit_execution_allowed": True,
        "candidate_enumeration_allowed": False,
        "crosswalk_pool_materialization_allowed": False,
        "labeling_allowed": False,
        "training_allowed": False,
    }:
        raise PermissionError("All-filer capacity audit gate contract changed")
    output = Path(config["output"])
    if output.exists():
        raise FileExistsError("Refusing to overwrite all-filer capacity audit")

    iapd = load_jsonl(Path(config["inputs"]["iapd_normalized"]["path"]))
    if len(iapd) != config["inputs"]["iapd_normalized"]["record_count"]:
        raise ValueError("IAPD row count mismatch")
    iapd_tokens = [tokens(row["entity_name_from_reference"]) for row in iapd]
    inverted: defaultdict[str, set[int]] = defaultdict(set)
    for index, current in enumerate(iapd_tokens):
        for token in current:
            inverted[token].add(index)
    best = [(0.0, "") for _ in iapd]
    second = [(0.0, "") for _ in iapd]
    edgar_count = 0
    with Path(config["inputs"]["edgar_identity_index"]["path"]).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            edgar_count += 1
            right = tokens(row["name"])
            candidates: set[int] = set()
            for token in right:
                candidates.update(inverted.get(token, ()))
            for index in candidates:
                left = iapd_tokens[index]
                score = len(left & right) / len(left | right) if left | right else 0.0
                update_top_two(best, second, index, score, row["cik"])
    if edgar_count != config["inputs"]["edgar_identity_index"]["record_count"]:
        raise ValueError("EDGAR identity-index row count mismatch")

    threshold = config["method"]["name_token_jaccard_minimum"]
    margin_min = config["method"]["runner_up_margin_minimum"]
    qualified: list[dict[str, Any]] = []
    for index, row in enumerate(iapd):
        score, cik = best[index]
        margin = score - second[index][0]
        if score >= threshold and margin >= margin_min:
            qualified.append(
                {
                    "cik": cik,
                    "host": row["normalized_host"],
                    "record": str(row["source_record_id"]),
                    "score": score,
                    "margin": margin,
                }
            )
    by_cik: defaultdict[str, int] = defaultdict(int)
    by_host: defaultdict[str, int] = defaultdict(int)
    for row in qualified:
        by_cik[row["cik"]] += 1
        by_host[row["host"]] += 1
    unique = [row for row in qualified if by_cik[row["cik"]] == 1 and by_host[row["host"]] == 1]
    existing = load_jsonl(Path(config["inputs"]["existing_ticker_crosswalk_pool"]["path"]))
    existing_pairs = {(row["cik"], row["normalized_host"]) for row in existing}
    overlap = sum((row["cik"], row["host"]) in existing_pairs for row in unique)
    fingerprint = hashlib.sha256(
        "\n".join(sorted(f"{row['cik']}|{row['record']}|{row['host']}" for row in unique)).encode()
    ).hexdigest()
    required = config["method"]["planning_reservoir_required"]
    result = {
        "analysis_id": config["audit_id"],
        "status": "PASS_CAPACITY_REFERENCE_ONLY" if len(unique) >= required else "FAIL_CAPACITY_REFERENCE_ONLY",
        "inputs": {"edgar_rows": edgar_count, "iapd_rows": len(iapd), "existing_pool_rows": len(existing)},
        "thresholds": {"name_token_jaccard_minimum": threshold, "runner_up_margin_minimum": margin_min},
        "capacity": {
            "threshold_qualified_rows_before_uniqueness": len(qualified),
            "unique_cik_and_host_rows": len(unique),
            "existing_pair_overlap": overlap,
            "net_new_rows_vs_existing_pairs": len(unique) - overlap,
            "planning_reservoir_required": required,
            "surplus_or_gap": len(unique) - required,
            "qualified_set_sha256": fingerprint,
            "identity_rows_emitted": 0,
        },
        "decision": {
            "capacity_gate_passed": len(unique) >= required,
            "candidate_enumeration_allowed": False,
            "crosswalk_pool_materialization_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".partial")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
