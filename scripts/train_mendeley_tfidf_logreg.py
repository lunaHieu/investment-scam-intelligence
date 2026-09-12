"""Train and evaluate a TF-IDF + Logistic Regression text baseline.

Hyperparameters are selected on validation only. Test is evaluated once after
selection. Only text_content is used as a feature.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


LABEL_SEMANTICS = (
    "Mendeley V2 source label: harmonized investment-related deceptive or suspicious "
    "content; not verified investment-scam ground truth for every record."
)


def read_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    splits = {"train": [], "validation": [], "test": []}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"record_id", "source_dataset", "text_content", "label", "partition"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(required)}")
        for row in reader:
            partition = row.get("partition")
            if partition in splits and row.get("label") in {"0", "1"}:
                splits[partition].append(row)
    if not all(splits.values()):
        raise ValueError("Expected non-empty train, validation and test partitions")
    return splits


def metrics(y_true, y_pred) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return {
        "row_count": len(y_true),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision_label_1": round(float(precision), 6),
        "recall_label_1": round(float(recall), 6),
        "f1_label_1": round(float(f1), 6),
    }


def texts(rows):
    return [row.get("text_content") or "" for row in rows]


def labels(rows):
    return [int(row["label"]) for row in rows]


def evaluate_by_source(classifier, matrix, rows) -> dict:
    predictions = classifier.predict(matrix)
    result = {}
    for source in sorted({row["source_dataset"] for row in rows}):
        indices = [index for index, row in enumerate(rows) if row["source_dataset"] == source]
        result[source] = metrics(
            [int(rows[index]["label"]) for index in indices],
            [int(predictions[index]) for index in indices],
        )
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    splits = read_rows(args.input)
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.995,
        max_features=100_000,
        sublinear_tf=True,
    )
    train_matrix = vectorizer.fit_transform(texts(splits["train"]))
    validation_matrix = vectorizer.transform(texts(splits["validation"]))
    test_matrix = vectorizer.transform(texts(splits["test"]))
    train_labels = labels(splits["train"])
    validation_labels = labels(splits["validation"])
    test_labels = labels(splits["test"])

    candidates = []
    best = None
    for class_weight in (None, "balanced"):
        for c_value in (0.25, 0.5, 1.0, 2.0, 4.0):
            classifier = LogisticRegression(
                C=c_value,
                class_weight=class_weight,
                solver="liblinear",
                max_iter=1000,
                random_state=20260912,
            )
            classifier.fit(train_matrix, train_labels)
            validation_metrics = metrics(validation_labels, classifier.predict(validation_matrix))
            candidate = {
                "C": c_value,
                "class_weight": class_weight,
                "validation": validation_metrics,
            }
            candidates.append(candidate)
            score = (validation_metrics["f1_label_1"], validation_metrics["accuracy"], -c_value)
            if best is None or score > best[0]:
                best = (score, classifier, candidate)

    assert best is not None
    classifier = best[1]
    selected = best[2]
    validation_predictions = classifier.predict(validation_matrix)
    test_predictions = classifier.predict(test_matrix)
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "task": "TF-IDF word unigram+bigram Logistic Regression on leakage-aware Mendeley group split V1",
        "label_semantics": LABEL_SEMANTICS,
        "feature_policy": "text_content only; source_dataset is used only for stratified reporting and never as a feature.",
        "selection_policy": "C and class_weight selected by validation F1 only; test was not used for selection.",
        "data": {
            "input": str(args.input),
            "partition_counts": {name: len(rows) for name, rows in splits.items()},
            "train_label_counts": dict(sorted(Counter(row["label"] for row in splits["train"]).items())),
        },
        "vectorizer": {
            "type": "tfidf",
            "ngram_range": [1, 2],
            "min_df": 2,
            "max_df": 0.995,
            "max_features": 100000,
            "sublinear_tf": True,
            "vocabulary_size": len(vectorizer.vocabulary_),
        },
        "selection_candidates": candidates,
        "selected_hyperparameters": {"C": selected["C"], "class_weight": selected["class_weight"]},
        "validation": metrics(validation_labels, validation_predictions),
        "test": metrics(test_labels, test_predictions),
        "test_by_source_dataset": evaluate_by_source(classifier, test_matrix, splits["test"]),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "vectorizer": vectorizer,
            "classifier": classifier,
            "metadata": {
                "label_semantics": LABEL_SEMANTICS,
                "selected_hyperparameters": report["selected_hyperparameters"],
            },
        },
        args.output_dir / "model.joblib",
    )
    (args.output_dir / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "vocabulary_size": report["vectorizer"]["vocabulary_size"],
        "selected_hyperparameters": report["selected_hyperparameters"],
        "validation": report["validation"],
        "test": report["test"],
        "test_by_source_dataset": report["test_by_source_dataset"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
