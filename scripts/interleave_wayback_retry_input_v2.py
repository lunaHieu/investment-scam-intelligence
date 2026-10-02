"""Reorder unresolved Wayback requests across branches without changing outcomes."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


BRANCHES = ("CONFIRMED_CANDIDATE", "LEGITIMATE_CANDIDATE")


def interleave_error_results(results: list[dict[str, object]]) -> list[dict[str, object]]:
    unresolved = {
        branch: sorted(
            [row for row in results if row.get("error") and row.get("reference_branch") == branch],
            key=lambda row: str(row["candidate_id"]),
        )
        for branch in BRANCHES
    }
    unknown = [
        row
        for row in results
        if row.get("error") and row.get("reference_branch") not in BRANCHES
    ]
    if unknown:
        raise ValueError("Unresolved result has an unknown reference branch")
    ordered: list[dict[str, object]] = []
    for index in range(max((len(rows) for rows in unresolved.values()), default=0)):
        for branch in BRANCHES:
            if index < len(unresolved[branch]):
                ordered.append(unresolved[branch][index])
    resolved = sorted(
        [row for row in results if not row.get("error")], key=lambda row: str(row["candidate_id"])
    )
    combined = ordered + resolved
    if len(combined) != len(results):
        raise ValueError("Interleaving changed result coverage")
    if {row["candidate_id"] for row in combined} != {row["candidate_id"] for row in results}:
        raise ValueError("Interleaving changed candidate IDs")
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    output = deepcopy(source)
    output["report_id"] = "WAYBACK_LANGUAGE_EXPANSION_AVAILABILITY_V2_INTERLEAVED_RETRY_INPUT"
    output["execution_order_only"] = {
        "parent_report": str(args.input),
        "parent_report_sha256": sha256_file(args.input),
        "policy": "ROUND_ROBIN_UNRESOLVED_REFERENCE_BRANCHES_THEN_RESOLVED_RESULTS",
        "semantic_outcomes_changed": False,
        "labels_created": 0,
    }
    output["results"] = interleave_error_results(source["results"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "unresolved_count": sum(bool(row.get("error")) for row in output["results"]),
                "first_unresolved_branches": [
                    row["reference_branch"]
                    for row in output["results"]
                    if row.get("error")
                ][:12],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
