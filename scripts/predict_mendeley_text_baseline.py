"""Run one text through the Mendeley V2 Naive Bayes baseline.

The result is a benchmark-label prediction, not an accusation or a legal finding.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{2,}")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def probability_label_one(model: dict[str, object], text: str) -> float:
    alpha = float(model["alpha"])
    vocabulary_size = int(model["vocabulary_size"])
    documents = model["class_document_counts"]
    totals = model["class_token_totals"]
    counts = model["class_token_counts"]
    total_documents = sum(int(value) for value in documents.values())
    scores: dict[str, float] = {}
    for label in ("0", "1"):
        score = math.log(int(documents[label]) / total_documents)
        denominator = int(totals[label]) + alpha * vocabulary_size
        for token, frequency in Counter(tokenize(text)).items():
            score += frequency * math.log((int(counts[label].get(token, 0)) + alpha) / denominator)
        scores[label] = score
    maximum = max(scores.values())
    zero = math.exp(scores["0"] - maximum)
    one = math.exp(scores["1"] - maximum)
    return one / (zero + one)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--text", required=True, help="Text to classify; do not include personal data.")
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    probability = probability_label_one(model, args.text)
    result = {
        "predicted_source_label": "1" if probability >= 0.5 else "0",
        "probability_source_label_1": round(probability, 4),
        "meaning": "Label 1 means Mendeley source benchmark: investment-related deceptive or suspicious content.",
        "limitation": "This is not a verified investment-scam, legal, or safety determination.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
