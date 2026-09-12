"""Train a transparent text-only Naive Bayes baseline on Mendeley V2.

This baseline learns the source's deceptive/suspicious benchmark label. It does
not claim to detect legally verified investment scams.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{2,}")
LABEL_SEMANTICS = (
    "Mendeley V2 source label: harmonized investment-related deceptive or suspicious "
    "content; not verified investment-scam ground truth for every record."
)


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def read_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    splits: dict[str, list[dict[str, str]]] = {"train": [], "validation": [], "test": []}
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        expected = {"text_content", "label", "partition", "record_id"}
        if reader.fieldnames is None or not expected.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(expected)}")
        for row in reader:
            partition = (row.get("partition") or "").strip()
            label = (row.get("label") or "").strip()
            if partition not in splits:
                continue
            if label not in {"0", "1"}:
                continue
            splits[partition].append(row)
    if not all(splits.values()):
        raise ValueError("Expected non-empty train, val and test partitions")
    return splits


def train(train_rows: list[dict[str, str]], min_token_frequency: int = 2) -> dict[str, object]:
    class_document_counts = Counter(row["label"] for row in train_rows)
    class_token_counts = {"0": Counter(), "1": Counter()}
    global_token_counts: Counter[str] = Counter()
    for row in train_rows:
        tokens = tokenize(row.get("text_content") or "")
        counts = Counter(tokens)
        class_token_counts[row["label"]].update(counts)
        global_token_counts.update(counts)
    vocabulary = {token for token, count in global_token_counts.items() if count >= min_token_frequency}
    filtered_counts = {
        label: {token: count for token, count in counts.items() if token in vocabulary}
        for label, counts in class_token_counts.items()
    }
    token_totals = {label: sum(counts.values()) for label, counts in filtered_counts.items()}
    return {
        "model_type": "multinomial_naive_bayes_text_only",
        "alpha": 1.0,
        "min_token_frequency": min_token_frequency,
        "vocabulary_size": len(vocabulary),
        "class_document_counts": dict(class_document_counts),
        "class_token_totals": token_totals,
        "class_token_counts": filtered_counts,
        "train_document_count": len(train_rows),
    }


def predict_probability_one(model: dict[str, object], text: str) -> float:
    vocabulary_size = int(model["vocabulary_size"])
    alpha = float(model["alpha"])
    class_docs = model["class_document_counts"]
    class_totals = model["class_token_totals"]
    token_counts = model["class_token_counts"]
    total_docs = sum(int(value) for value in class_docs.values())
    scores: dict[str, float] = {}
    for label in ("0", "1"):
        score = math.log(int(class_docs[label]) / total_docs)
        denominator = int(class_totals[label]) + alpha * vocabulary_size
        for token, count in Counter(tokenize(text)).items():
            numerator = int(token_counts[label].get(token, 0)) + alpha
            score += count * math.log(numerator / denominator)
        scores[label] = score
    maximum = max(scores.values())
    exp_zero = math.exp(scores["0"] - maximum)
    exp_one = math.exp(scores["1"] - maximum)
    return exp_one / (exp_zero + exp_one)


def evaluate(model: dict[str, object], rows: list[dict[str, str]]) -> dict[str, object]:
    matrix = {"tn": 0, "fp": 0, "fn": 0, "tp": 0}
    examples: list[dict[str, object]] = []
    for row in rows:
        probability = predict_probability_one(model, row.get("text_content") or "")
        predicted = "1" if probability >= 0.5 else "0"
        actual = row["label"]
        if actual == "1" and predicted == "1":
            matrix["tp"] += 1
        elif actual == "0" and predicted == "1":
            matrix["fp"] += 1
        elif actual == "1" and predicted == "0":
            matrix["fn"] += 1
        else:
            matrix["tn"] += 1
        if actual != predicted and len(examples) < 10:
            examples.append({
                "record_id": row["record_id"], "actual_label": actual, "predicted_label": predicted,
                "probability_label_1": round(probability, 4),
                "text_preview": (row.get("text_content") or "")[:240],
            })
    precision = matrix["tp"] / (matrix["tp"] + matrix["fp"]) if matrix["tp"] + matrix["fp"] else 0.0
    recall = matrix["tp"] / (matrix["tp"] + matrix["fn"]) if matrix["tp"] + matrix["fn"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (matrix["tp"] + matrix["tn"]) / len(rows)
    return {
        "row_count": len(rows), "threshold_label_1": 0.5, "confusion_matrix": matrix,
        "accuracy": round(accuracy, 6), "precision_label_1": round(precision, 6),
        "recall_label_1": round(recall, 6), "f1_label_1": round(f1, 6),
        "misclassified_examples": examples,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    splits = read_rows(args.input)
    model = train(splits["train"])
    results = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "task": "text-only baseline on Mendeley V2 source label",
        "label_semantics": LABEL_SEMANTICS,
        "feature_policy": "text_content tokens only; no metadata, source IDs, partitions, filter scores or evidence fields.",
        "split_policy": "Uses source-provided train/val/test partition. Validation and test are benchmark splits, not ISI Gold.",
        "model_summary": {key: value for key, value in model.items() if key != "class_token_counts"},
        "validation": evaluate(model, splits["validation"]),
        "test": evaluate(model, splits["test"]),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "model.json").write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    (args.output_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact_validation = {key: value for key, value in results["validation"].items() if key != "misclassified_examples"}
    compact_test = {key: value for key, value in results["test"].items() if key != "misclassified_examples"}
    print(json.dumps({
        "output_dir": str(args.output_dir), "vocabulary_size": model["vocabulary_size"],
        "validation": compact_validation, "test": compact_test,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
