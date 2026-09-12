"""Paired error comparison of Naive Bayes and TF-IDF Logistic Regression."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from train_mendeley_text_baseline import predict_probability_one


EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")


def redact(text: str) -> str:
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = URL_RE.sub("[URL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return " ".join(text.split())[:320].rstrip()


def exact_mcnemar_p_value(nb_only_correct: int, lr_only_correct: int) -> float:
    """Two-sided exact McNemar/binomial p-value for discordant pairs."""
    discordant = nb_only_correct + lr_only_correct
    if discordant == 0:
        return 1.0
    lower = min(nb_only_correct, lr_only_correct)
    tail = sum(math.comb(discordant, value) for value in range(lower + 1)) / (2 ** discordant)
    return min(1.0, 2.0 * tail)


def read_test_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"record_id", "source_dataset", "text_content", "label", "partition"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(required)}")
        return [row for row in reader if row.get("partition") == "test" and row.get("label") in {"0", "1"}]


def summarize_examples(items: list[dict], limit: int = 20) -> list[dict]:
    ranked = sorted(
        items,
        key=lambda item: (-item["wrong_model_confidence"], item["record_id"]),
    )
    return ranked[:limit]


def main() -> int:
    import joblib

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--nb-model", type=Path, required=True)
    parser.add_argument("--lr-model", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    rows = read_test_rows(args.input)
    nb_model = json.loads(args.nb_model.read_text(encoding="utf-8"))
    lr_bundle = joblib.load(args.lr_model)
    vectorizer = lr_bundle["vectorizer"]
    classifier = lr_bundle["classifier"]
    lr_matrix = vectorizer.transform([row.get("text_content") or "" for row in rows])
    lr_probabilities = classifier.predict_proba(lr_matrix)[:, 1]

    category_counts = Counter()
    source_counts: dict[str, Counter] = defaultdict(Counter)
    examples: dict[str, list[dict]] = defaultdict(list)
    for index, row in enumerate(rows):
        actual = row["label"]
        nb_probability = predict_probability_one(nb_model, row.get("text_content") or "")
        lr_probability = float(lr_probabilities[index])
        nb_prediction = "1" if nb_probability >= 0.5 else "0"
        lr_prediction = "1" if lr_probability >= 0.5 else "0"
        nb_correct = nb_prediction == actual
        lr_correct = lr_prediction == actual
        if nb_correct and lr_correct:
            category = "both_correct"
        elif not nb_correct and lr_correct:
            category = "lr_fixed_nb_error"
        elif nb_correct and not lr_correct:
            category = "lr_regression"
        else:
            category = "both_wrong"
        category_counts[category] += 1
        source_counts[row["source_dataset"]][category] += 1
        if category != "both_correct":
            wrong_probability = nb_probability if category == "lr_fixed_nb_error" else lr_probability
            wrong_prediction = nb_prediction if category == "lr_fixed_nb_error" else lr_prediction
            wrong_confidence = wrong_probability if wrong_prediction == "1" else 1.0 - wrong_probability
            examples[category].append({
                "record_id": row["record_id"],
                "source_dataset": row["source_dataset"],
                "actual_label": actual,
                "naive_bayes_prediction": nb_prediction,
                "naive_bayes_probability_label_1": round(nb_probability, 6),
                "tfidf_logreg_prediction": lr_prediction,
                "tfidf_logreg_probability_label_1": round(lr_probability, 6),
                "wrong_model_confidence": round(wrong_confidence, 6),
                "redacted_text_preview": redact(row.get("text_content") or ""),
            })

    nb_only = category_counts["lr_regression"]
    lr_only = category_counts["lr_fixed_nb_error"]
    p_value = exact_mcnemar_p_value(nb_only, lr_only)
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Paired comparison on the exact same leakage-aware Mendeley group-split V1 test records.",
        "test_rows": len(rows),
        "category_counts": dict(category_counts),
        "net_errors_removed_by_logreg": lr_only - nb_only,
        "mcnemar_exact": {
            "nb_only_correct_lr_wrong": nb_only,
            "lr_only_correct_nb_wrong": lr_only,
            "discordant_pairs": nb_only + lr_only,
            "two_sided_p_value": p_value,
            "alpha": 0.05,
            "statistically_significant": p_value < 0.05,
        },
        "by_source_dataset": {
            source: dict(counts) for source, counts in sorted(source_counts.items())
        },
        "examples": {
            category: summarize_examples(items)
            for category, items in examples.items()
        },
        "interpretation_rule": "Statistical significance here concerns agreement with Mendeley source labels only, not verified real-world scam detection.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Đối chiếu lỗi từng mẫu — Naive Bayes và TF-IDF Logistic Regression",
        "",
        "## Kết quả cặp trên cùng test",
        "",
        "| Trạng thái | Số mẫu |",
        "| --- | ---: |",
        f"| Cả hai đúng | {category_counts['both_correct']} |",
        f"| Logistic Regression sửa được lỗi của Naive Bayes | {lr_only} |",
        f"| Logistic Regression làm sai mẫu Naive Bayes từng đúng | {nb_only} |",
        f"| Cả hai cùng sai | {category_counts['both_wrong']} |",
        "",
        f"Model mới giảm ròng {lr_only - nb_only} lỗi. Exact McNemar p-value = {p_value:.6f}; "
        + ("chênh lệch có ý nghĩa ở ngưỡng 0,05." if p_value < 0.05 else "chưa đủ bằng chứng về chênh lệch có ý nghĩa ở ngưỡng 0,05."),
        "",
        "Kiểm định này chỉ đo mức khớp với nhãn nguồn Mendeley, không chứng minh khả năng phát hiện lừa đảo thực tế.",
        "",
        "## Phân bố theo nguồn",
        "",
        "| Nguồn | Cả hai đúng | LR sửa được | LR làm sai thêm | Cả hai sai |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for source, counts in sorted(source_counts.items()):
        lines.append(
            f"| {source} | {counts['both_correct']} | {counts['lr_fixed_nb_error']} | "
            f"{counts['lr_regression']} | {counts['both_wrong']} |"
        )
    titles = {
        "lr_fixed_nb_error": "Các mẫu model mới sửa được",
        "lr_regression": "Các mẫu model mới làm sai thêm",
        "both_wrong": "Các mẫu cả hai cùng sai",
    }
    for category in ("lr_fixed_nb_error", "lr_regression", "both_wrong"):
        lines.extend(["", f"## {titles[category]}", ""])
        for item in report["examples"].get(category, [])[:10]:
            lines.extend([
                f"### {item['record_id']} — {item['source_dataset']}",
                "",
                f"- Actual `{item['actual_label']}`; NB `{item['naive_bayes_prediction']}` (p1={item['naive_bayes_probability_label_1']:.3f}); LR `{item['tfidf_logreg_prediction']}` (p1={item['tfidf_logreg_probability_label_1']:.3f}).",
                f"- Preview đã ẩn định danh: {item['redacted_text_preview']}",
                "",
            ])
    lines.extend([
        "## Quyết định",
        "",
        "- Logistic Regression tốt hơn nhẹ về tổng số lỗi, nhưng hai model trao đổi nhiều lỗi khác nhau.",
        "- Giữ cả hai kết quả để tái lập; chọn Logistic Regression làm baseline nội bộ chính vì cross-source macro tốt hơn.",
        "- Các mẫu cả hai cùng sai và các regression tự tin cao phải được dùng làm error set; không sửa raw label nếu chưa có evidence độc lập.",
        "",
    ])
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "test_rows": len(rows),
        "category_counts": report["category_counts"],
        "net_errors_removed_by_logreg": report["net_errors_removed_by_logreg"],
        "mcnemar_exact": report["mcnemar_exact"],
        "outputs": {"json": str(args.output_json), "markdown": str(args.output_md)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
