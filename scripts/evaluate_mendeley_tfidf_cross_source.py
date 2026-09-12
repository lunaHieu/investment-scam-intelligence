"""Evaluate TF-IDF Logistic Regression with each source held out from training."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from train_mendeley_tfidf_logreg import labels, metrics, read_rows, texts


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True, help="Main run results.json with selected hyperparameters")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    splits = read_rows(args.input)
    main_results = json.loads(args.results.read_text(encoding="utf-8"))
    selected = main_results["selected_hyperparameters"]
    sources = sorted({row["source_dataset"] for rows in splits.values() for row in rows})
    source_results = {}
    for held_out in sources:
        train_rows = [row for row in splits["train"] if row["source_dataset"] != held_out]
        test_rows = [row for row in splits["test"] if row["source_dataset"] == held_out]
        vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.995,
            max_features=100_000,
            sublinear_tf=True,
        )
        train_matrix = vectorizer.fit_transform(texts(train_rows))
        test_matrix = vectorizer.transform(texts(test_rows))
        classifier = LogisticRegression(
            C=float(selected["C"]),
            class_weight=selected["class_weight"],
            solver="liblinear",
            max_iter=1000,
            random_state=20260912,
        )
        classifier.fit(train_matrix, labels(train_rows))
        source_results[held_out] = {
            "train_rows_from_other_sources": len(train_rows),
            "held_out_test_rows": len(test_rows),
            "vocabulary_size": len(vectorizer.vocabulary_),
            "metrics": metrics(labels(test_rows), classifier.predict(test_matrix)),
        }

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Each source_dataset is excluded from train; hyperparameters were inherited from validation selection in the main run.",
        "selected_hyperparameters": selected,
        "by_held_out_source": source_results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
