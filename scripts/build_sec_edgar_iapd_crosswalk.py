"""Build a deterministic EDGAR-to-IAPD identity crosswalk without creating labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


STOP_TOKENS = {
    "adviser",
    "advisers",
    "advisor",
    "advisors",
    "asset",
    "capital",
    "co",
    "company",
    "corp",
    "corporation",
    "financial",
    "group",
    "holding",
    "holdings",
    "inc",
    "incorporated",
    "investment",
    "investments",
    "limited",
    "llc",
    "llp",
    "lp",
    "ltd",
    "management",
    "partners",
    "plc",
    "the",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokens(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value).casefold())
        if token not in STOP_TOKENS and len(token) > 1
    }


def stable_key(seed: str, cik: str, host: str) -> str:
    return hashlib.sha256(
        f"{seed}|LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE|sec_edgar_company_submissions|{cik}|{host}".encode(
            "utf-8"
        )
    ).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edgar-tickers", type=Path, required=True)
    parser.add_argument("--iapd-normalized", type=Path, required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--pool-output", type=Path, required=True)
    parser.add_argument("--shortlist-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--shortlist-size", type=int, default=20)
    args = parser.parse_args()
    for output in (args.pool_output, args.shortlist_output, args.report):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    edgar = json.loads(args.edgar_tickers.read_text(encoding="utf-8"))
    if edgar.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise ValueError("Unexpected SEC company-ticker field contract")
    edgar_rows = edgar["data"]
    edgar_token_sets: list[set[str]] = []
    inverted: defaultdict[str, set[int]] = defaultdict(set)
    for index, row in enumerate(edgar_rows):
        current = tokens(row[1])
        edgar_token_sets.append(current)
        for token in current:
            inverted[token].add(index)
    iapd_rows = [
        json.loads(line)
        for line in args.iapd_normalized.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pool: list[dict] = []
    for row in iapd_rows:
        left = tokens(row["entity_name_from_reference"])
        candidate_indices: set[int] = set()
        for token in left:
            candidate_indices.update(inverted[token])
        scored: list[tuple[float, int]] = []
        for index in candidate_indices:
            right = edgar_token_sets[index]
            score = len(left & right) / len(left | right) if left | right else 0.0
            scored.append((score, index))
        scored.sort(key=lambda item: (-item[0], item[1]))
        if not scored:
            continue
        best_score, best_index = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        margin = best_score - second_score
        if best_score < 0.8 or margin < 0.15:
            continue
        cik, edgar_name, ticker, exchange = edgar_rows[best_index]
        cik_text = f"{int(cik):010d}"
        host = row["normalized_host"]
        pool.append(
            {
                "cik": cik_text,
                "edgar_entity_name": edgar_name,
                "ticker": ticker,
                "exchange": exchange,
                "iapd_source_record_id": row["source_record_id"],
                "iapd_entity_name": row["entity_name_from_reference"],
                "candidate_url": row["candidate_url"],
                "normalized_host": host,
                "name_token_jaccard": round(best_score, 6),
                "runner_up_margin": round(margin, 6),
                "shared_distinctive_tokens": sorted(left & edgar_token_sets[best_index]),
                "selection_key": stable_key(args.seed, cik_text, host),
                "identity_linkage_status": "PRELIMINARY_INDEPENDENT_REVIEW_REQUIRED",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
            }
        )
    by_cik: defaultdict[str, list[dict]] = defaultdict(list)
    by_host: defaultdict[str, list[dict]] = defaultdict(list)
    for row in pool:
        by_cik[row["cik"]].append(row)
        by_host[row["normalized_host"]].append(row)
    unique_pool = [
        row
        for row in pool
        if len(by_cik[row["cik"]]) == 1 and len(by_host[row["normalized_host"]]) == 1
    ]
    unique_pool.sort(key=lambda row: row["selection_key"])
    if len(unique_pool) < args.shortlist_size:
        raise ValueError(
            f"Insufficient unambiguous EDGAR/IAPD crosswalk rows: {len(unique_pool)}"
        )
    shortlist = unique_pool[: args.shortlist_size]
    write_jsonl(args.pool_output, unique_pool)
    write_jsonl(args.shortlist_output, shortlist)
    report = {
        "analysis_id": "ISI_TARGET_TEXT_CORPUS_V1_SEC_EDGAR_IAPD_CROSSWALK_V1",
        "status": "FROZEN_PRELIMINARY_IDENTITY_SHORTLIST_REVIEW_REQUIRED",
        "inputs": {
            "edgar_tickers": {
                "path": str(args.edgar_tickers),
                "sha256": sha256_file(args.edgar_tickers),
                "record_count": len(edgar_rows),
            },
            "iapd_normalized": {
                "path": str(args.iapd_normalized),
                "sha256": sha256_file(args.iapd_normalized),
                "record_count": len(iapd_rows),
            },
        },
        "selection_seed": args.seed,
        "quality": {
            "threshold_jaccard_minimum": 0.8,
            "runner_up_margin_minimum": 0.15,
            "unambiguous_pool_count": len(unique_pool),
            "shortlist_count": len(shortlist),
            "unique_shortlist_ciks": len({row["cik"] for row in shortlist}),
            "unique_shortlist_hosts": len({row["normalized_host"] for row in shortlist}),
        },
        "outputs": {
            "pool": {"path": str(args.pool_output), "sha256": sha256_file(args.pool_output)},
            "shortlist": {
                "path": str(args.shortlist_output),
                "sha256": sha256_file(args.shortlist_output),
            },
        },
        "review_gate": {
            "independent_identity_review_required": True,
            "submissions_download_complete": False,
            "candidate_enumeration_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
