"""Compare Naive Bayes and TF-IDF Logistic Regression from saved reports."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expanded(matrix: dict) -> dict:
    tn, fp, fn, tp = (matrix[name] for name in ("tn", "fp", "fn", "tp"))
    recall_one = tp / (tp + fn) if tp + fn else 0.0
    recall_zero = tn / (tn + fp) if tn + fp else 0.0
    precision_one = tp / (tp + fp) if tp + fp else 0.0
    precision_zero = tn / (tn + fn) if tn + fn else 0.0
    f1_one = 2 * precision_one * recall_one / (precision_one + recall_one) if precision_one + recall_one else 0.0
    f1_zero = 2 * precision_zero * recall_zero / (precision_zero + recall_zero) if precision_zero + recall_zero else 0.0
    return {
        "accuracy": round((tp + tn) / (tp + tn + fp + fn), 6),
        "f1_label_1": round(f1_one, 6),
        "macro_f1": round((f1_one + f1_zero) / 2, 6),
        "balanced_accuracy": round((recall_one + recall_zero) / 2, 6),
    }


def comparison(left: dict, right: dict) -> dict:
    return {
        "naive_bayes": left,
        "tfidf_logreg": right,
        "delta_logreg_minus_nb": {
            metric: round(right[metric] - left[metric], 6)
            for metric in ("accuracy", "f1_label_1", "macro_f1", "balanced_accuracy")
        },
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nb-results", type=Path, required=True)
    parser.add_argument("--nb-by-source", type=Path, required=True)
    parser.add_argument("--nb-cross-source", type=Path, required=True)
    parser.add_argument("--lr-results", type=Path, required=True)
    parser.add_argument("--lr-cross-source", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    nb_results = load(args.nb_results)
    nb_by_source = load(args.nb_by_source)["test_metrics_by_source_dataset"]
    nb_cross = load(args.nb_cross_source)["leave_one_source_out"]
    lr_results = load(args.lr_results)
    lr_by_source = lr_results["test_by_source_dataset"]
    lr_cross = load(args.lr_cross_source)["by_held_out_source"]

    same_test = comparison(
        expanded(nb_results["test"]["confusion_matrix"]),
        expanded(lr_results["test"]["confusion_matrix"]),
    )
    by_source = {
        source: comparison(
            expanded(nb_by_source[source]["confusion_matrix"]),
            expanded(lr_by_source[source]["confusion_matrix"]),
        )
        for source in sorted(nb_by_source)
    }
    cross_source = {
        source: comparison(
            expanded(nb_cross[source]["metrics"]["confusion_matrix"]),
            expanded(lr_cross[source]["metrics"]["confusion_matrix"]),
        )
        for source in sorted(nb_cross)
    }
    cross_macro = {
        model: {
            metric: round(statistics.mean(
                values[model][metric] for values in cross_source.values()
            ), 6)
            for metric in ("accuracy", "f1_label_1", "macro_f1", "balanced_accuracy")
        }
        for model in ("naive_bayes", "tfidf_logreg")
    }
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Both models use text_content only and the same leakage-aware group split V1. Hyperparameters were selected on validation, not test.",
        "same_test": same_test,
        "same_test_by_source": by_source,
        "leave_one_source_out": cross_source,
        "leave_one_source_out_macro_across_sources": cross_macro,
        "decision": "TF-IDF Logistic Regression is the stronger internal baseline overall, but neither model is suitable for deployment or verified-scam claims without curated external evaluation.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    nb = same_test["naive_bayes"]
    lr = same_test["tfidf_logreg"]
    lines = [
        "# So sánh hai baseline text — Mendeley group split V1",
        "",
        "## Kết luận",
        "",
        "TF-IDF + Logistic Regression được chọn làm baseline nội bộ mạnh hơn. Cả hai model dùng đúng cùng group split, chỉ nhận `text_content`, và không dùng test để chọn tham số. Kết quả này vẫn là benchmark theo nhãn Mendeley, không phải khả năng xác minh lừa đảo thực tế.",
        "",
        "## Cùng một test cố định",
        "",
        "| Model | Accuracy | F1 label 1 | Macro-F1 | Balanced accuracy |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Naive Bayes | {nb['accuracy']:.1%} | {nb['f1_label_1']:.1%} | {nb['macro_f1']:.1%} | {nb['balanced_accuracy']:.1%} |",
        f"| TF-IDF + Logistic Regression | {lr['accuracy']:.1%} | {lr['f1_label_1']:.1%} | {lr['macro_f1']:.1%} | {lr['balanced_accuracy']:.1%} |",
        "",
        "Mức tăng F1 label 1 chỉ khoảng 0,46 điểm phần trăm; cải thiện trong test quen thuộc là nhỏ.",
        "",
        "## Test cố định theo nguồn (F1 label 1)",
        "",
        "| Nguồn | Naive Bayes | TF-IDF LogReg | Chênh lệch |",
        "| --- | ---: | ---: | ---: |",
    ]
    for source, values in by_source.items():
        left = values["naive_bayes"]["f1_label_1"]
        right = values["tfidf_logreg"]["f1_label_1"]
        lines.append(f"| {source} | {left:.1%} | {right:.1%} | {right-left:+.1%} |")
    lines.extend([
        "",
        "## Leave-one-source-out (F1 label 1)",
        "",
        "| Nguồn bị loại hoàn toàn khỏi train | Naive Bayes | TF-IDF LogReg | Chênh lệch |",
        "| --- | ---: | ---: | ---: |",
    ])
    for source, values in cross_source.items():
        left = values["naive_bayes"]["f1_label_1"]
        right = values["tfidf_logreg"]["f1_label_1"]
        lines.append(f"| {source} | {left:.1%} | {right:.1%} | {right-left:+.1%} |")
    nb_macro = cross_macro["naive_bayes"]
    lr_macro = cross_macro["tfidf_logreg"]
    lines.extend([
        "",
        f"Trung bình F1 label 1 qua năm nguồn tăng từ {nb_macro['f1_label_1']:.1%} lên {lr_macro['f1_label_1']:.1%}. Tuy nhiên fake-profile giảm mạnh và Twitter bot vẫn gần mức ngẫu nhiên. Không model nào tổng quát ổn định trên mọi nguồn.",
        "",
        "## Quyết định cho đề tài",
        "",
        "- Giữ Naive Bayes làm baseline tối giản để tái lập.",
        "- Dùng TF-IDF + Logistic Regression làm baseline nội bộ chính.",
        "- Không gọi output là xác suất lừa đảo và chưa triển khai cho người dùng.",
        "- Bước đánh giá quyết định vẫn là curated/external cases có evidence độc lập.",
        "",
    ])
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "same_test": same_test,
        "leave_one_source_out_macro_across_sources": cross_macro,
        "outputs": {"json": str(args.output_json), "markdown": str(args.output_md)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
