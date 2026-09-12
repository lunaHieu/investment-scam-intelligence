"""Evaluate the Mendeley text baseline by source dataset without using source as a feature."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train_mendeley_text_baseline import evaluate, read_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(args.input)["test"]:
        groups[row["source_dataset"]].append(row)
    results = {
        "policy": "source_dataset is used only to stratify evaluation; it is never an input feature.",
        "test_metrics_by_source_dataset": {
            source: evaluate(model, rows) for source, rows in sorted(groups.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {
        source: {key: value for key, value in result.items() if key not in {"confusion_matrix", "misclassified_examples"}}
        for source, result in results["test_metrics_by_source_dataset"].items()
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
