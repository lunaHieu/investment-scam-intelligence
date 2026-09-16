"""Verify that baseline V2 validation selection is frozen before test access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mendeley_text_baseline_v2_common import (
    CANDIDATES,
    EXPECTED_PARTITION_COUNTS,
    EXPECTED_SPLIT_SHA256,
    candidate_score,
    sha256_file,
    validate_frozen_selection,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    args = parser.parse_args()
    if sha256_file(args.input) != EXPECTED_SPLIT_SHA256:
        raise ValueError("Frozen group_split_v2 hash mismatch")
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    validate_frozen_selection(selection, args.selection)
    if not all(selection["quality_gates"].values()):
        raise ValueError("Selection contains a failed quality gate")
    if selection["data_access"]["partition_counts_scanned"] != EXPECTED_PARTITION_COUNTS:
        raise ValueError("Selection partition scan count mismatch")
    if selection["predeclared_candidates"] != [dict(value) for value in CANDIDATES]:
        raise ValueError("Predeclared candidate grid mismatch")
    candidate_results = selection["candidate_results"]
    if len(candidate_results) != len(CANDIDATES):
        raise ValueError("Candidate result count mismatch")
    expected = max(
        candidate_results,
        key=lambda report: candidate_score(report, report["candidate_index"]),
    )
    if expected["candidate_index"] != selection["selected_candidate_index"]:
        raise ValueError("Stored selected candidate is not the validation winner")
    if expected["hyperparameters"] != selection["selected_hyperparameters"]:
        raise ValueError("Stored selected hyperparameters mismatch")
    if any("test" in report for report in candidate_results):
        raise ValueError("Candidate result unexpectedly contains test metrics")
    if selection["safety_contract"] != {
        "model_artifact_created": False,
        "network_operations": 0,
        "raw_files_modified": False,
        "split_file_modified": False,
        "test_metrics_created": False,
        "test_opened": False,
    }:
        raise ValueError("Selection safety contract mismatch")
    print(
        json.dumps(
            {
                "status": "VALID_FROZEN_SELECTION_TEST_UNOPENED",
                "selection_sha256": sha256_file(args.selection),
                "selection_digest": selection["selection_digest"],
                "selected_candidate_index": selection["selected_candidate_index"],
                "selected_hyperparameters": selection["selected_hyperparameters"],
                "test_opened": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
