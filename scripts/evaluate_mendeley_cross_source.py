"""Measure cross-source transfer for the Mendeley text baseline.

For each source dataset, train on all other source datasets' training rows and
evaluate on that source's test rows. Source IDs are split keys, never features.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train_mendeley_text_baseline import evaluate, read_rows, train


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    splits = read_rows(args.input)
    test_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in splits["test"]:
        test_by_source[row["source_dataset"]].append(row)
    results: dict[str, object] = {}
    for held_out_source, test_rows in sorted(test_by_source.items()):
        train_rows = [row for row in splits["train"] if row["source_dataset"] != held_out_source]
        model = train(train_rows)
        results[held_out_source] = {
            "train_rows_from_other_sources": len(train_rows),
            "held_out_test_rows": len(test_rows),
            "metrics": evaluate(model, test_rows),
        }
    report = {
        "policy": "source_dataset is used solely to define held-out evaluation; it is never a predictive feature.",
        "interpretation": "This is a robustness diagnostic for the Mendeley benchmark, not ISI Gold evaluation.",
        "leave_one_source_out": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {
        source: {
            "train_rows_from_other_sources": value["train_rows_from_other_sources"],
            "held_out_test_rows": value["held_out_test_rows"],
            **{metric: score for metric, score in value["metrics"].items() if metric not in {"confusion_matrix", "misclassified_examples"}},
        }
        for source, value in results.items()
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
