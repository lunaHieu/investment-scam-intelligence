"""Create a disjoint reference pool by removing hosts reserved for another channel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def remove_reserved_hosts(pool: list[dict], reserved: list[dict]) -> tuple[list[dict], set[str]]:
    reserved_hosts = {str(row["normalized_host"]).casefold().rstrip(".") for row in reserved}
    output = [
        row
        for row in pool
        if str(row["normalized_host"]).casefold().rstrip(".") not in reserved_hosts
    ]
    return output, reserved_hosts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--reserved", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.output, args.report):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    pool = load_jsonl(args.pool)
    reserved = load_jsonl(args.reserved)
    output, reserved_hosts = remove_reserved_hosts(pool, reserved)
    removed = len(pool) - len(output)
    if len({row["normalized_host"] for row in reserved}) < 10:
        raise ValueError("Reserved channel has fewer than 10 unique hosts")
    if len(output) < 10:
        raise ValueError("Disjoint pool has fewer than 10 rows")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output),
        encoding="utf-8",
    )
    report = {
        "analysis_id": "ISI_TARGET_TEXT_CORPUS_V1_REFERENCE_HOST_SEPARATION_V1",
        "status": "FROZEN_DISJOINT_REFERENCE_POOL_UNLABELED",
        "inputs": {
            "pool": {"path": str(args.pool), "sha256": sha256_file(args.pool), "record_count": len(pool)},
            "reserved": {
                "path": str(args.reserved),
                "sha256": sha256_file(args.reserved),
                "record_count": len(reserved),
                "unique_host_count": len(reserved_hosts),
            },
        },
        "output": {
            "path": str(args.output),
            "sha256": sha256_file(args.output),
            "record_count": len(output),
        },
        "removed_pool_rows": removed,
        "remaining_reserved_host_overlap": len(
            {row["normalized_host"] for row in output} & reserved_hosts
        ),
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
