"""Analyze false positives and false negatives for the text baseline."""

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

from train_mendeley_text_baseline import evaluate, predict_probability_one, tokenize


EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
THEME_TERMS = {
    "account_security": {"account", "bank", "banking", "login", "password", "security", "verify", "verification"},
    "investment_promotion": {"invest", "investment", "money", "profit", "return", "stock", "trading", "wealth"},
    "urgency_or_action": {"act", "click", "immediately", "limited", "now", "today", "urgent", "update"},
}


def redact(text: str) -> str:
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = URL_RE.sub("[URL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return " ".join(text.split())[:320].rstrip()


def themes(text: str) -> list[str]:
    tokens = tokenize(text)
    token_set = set(tokens)
    found = [name for name, terms in THEME_TERMS.items() if token_set.intersection(terms)]
    if len(tokens) <= 12:
        found.append("short_or_low_context")
    if not found:
        found.append("other")
    return found


def token_evidence(model: dict, text: str, limit: int = 5) -> dict[str, list[dict[str, float]]]:
    alpha = float(model["alpha"])
    vocab_size = int(model["vocabulary_size"])
    totals = model["class_token_totals"]
    counts = model["class_token_counts"]
    contributions = []
    for token, frequency in Counter(tokenize(text)).items():
        if token not in counts["0"] and token not in counts["1"]:
            continue
        p_zero = (int(counts["0"].get(token, 0)) + alpha) / (int(totals["0"]) + alpha * vocab_size)
        p_one = (int(counts["1"].get(token, 0)) + alpha) / (int(totals["1"]) + alpha * vocab_size)
        contributions.append((token, frequency * math.log(p_one / p_zero)))
    positive = sorted((item for item in contributions if item[1] > 0), key=lambda item: -item[1])[:limit]
    negative = sorted((item for item in contributions if item[1] < 0), key=lambda item: item[1])[:limit]
    return {
        "toward_label_1": [{"token": token, "log_odds": round(score, 4)} for token, score in positive],
        "toward_label_0": [{"token": token, "log_odds": round(score, 4)} for token, score in negative],
    }


def confidence_bucket(probability: float, predicted: str) -> str:
    confidence = probability if predicted == "1" else 1.0 - probability
    if confidence >= 0.99:
        return "0.99-1.00"
    if confidence >= 0.90:
        return "0.90-0.99"
    if confidence >= 0.75:
        return "0.75-0.90"
    if confidence >= 0.60:
        return "0.60-0.75"
    return "0.50-0.60"


def read_test_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"record_id", "source_dataset", "text_content", "label", "partition"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(required)}")
        return [row for row in reader if row.get("partition") == "test" and row.get("label") in {"0", "1"}]


def metric_without_examples(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key != "misclassified_examples"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    rows = read_test_rows(args.input)
    model = json.loads(args.model.read_text(encoding="utf-8"))
    errors = []
    for row in rows:
        probability = predict_probability_one(model, row.get("text_content") or "")
        predicted = "1" if probability >= 0.5 else "0"
        if predicted == row["label"]:
            continue
        error_type = "false_positive" if predicted == "1" else "false_negative"
        confidence = probability if predicted == "1" else 1.0 - probability
        text = row.get("text_content") or ""
        errors.append({
            "record_id": row["record_id"],
            "source_dataset": row["source_dataset"],
            "actual_label": row["label"],
            "predicted_label": predicted,
            "error_type": error_type,
            "probability_label_1": round(probability, 6),
            "prediction_confidence": round(confidence, 6),
            "confidence_bucket": confidence_bucket(probability, predicted),
            "themes": themes(text),
            "token_evidence": token_evidence(model, text),
            "redacted_text_preview": redact(text),
        })

    errors.sort(key=lambda item: (-item["prediction_confidence"], item["record_id"]))
    by_source = {}
    for source in sorted({row["source_dataset"] for row in rows}):
        source_rows = [row for row in rows if row["source_dataset"] == source]
        source_errors = [item for item in errors if item["source_dataset"] == source]
        by_source[source] = {
            "metrics": metric_without_examples(evaluate(model, source_rows)),
            "false_positives": sum(item["error_type"] == "false_positive" for item in source_errors),
            "false_negatives": sum(item["error_type"] == "false_negative" for item in source_errors),
            "high_confidence_errors_gte_0_90": sum(item["prediction_confidence"] >= 0.90 for item in source_errors),
        }

    theme_counts = Counter(theme for item in errors for theme in item["themes"])
    type_counts = Counter(item["error_type"] for item in errors)
    confidence_counts = Counter(item["confidence_bucket"] for item in errors)
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Group-split V1 test errors for the Mendeley source benchmark label; not verified scam ground truth.",
        "test_rows": len(rows),
        "total_errors": len(errors),
        "error_type_counts": dict(sorted(type_counts.items())),
        "high_confidence_errors_gte_0_90": sum(item["prediction_confidence"] >= 0.90 for item in errors),
        "confidence_bucket_counts": dict(sorted(confidence_counts.items())),
        "theme_counts_nonexclusive": dict(theme_counts.most_common()),
        "by_source_dataset": by_source,
        "highest_confidence_errors": errors[:30],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Phân tích lỗi baseline trên Mendeley group split V1",
        "",
        "## Kết luận nhanh",
        "",
        f"Test có {len(rows):,} mẫu và {len(errors):,} lỗi: "
        f"{type_counts['false_positive']} false positives, {type_counts['false_negative']} false negatives. "
        f"Có {report['high_confidence_errors_gte_0_90']} lỗi mà model tự tin từ 90% trở lên.",
        "",
        "Các nhãn vẫn là benchmark deceptive/suspicious của Mendeley, không phải ground truth lừa đảo đã xác minh.",
        "",
        "## Theo nguồn",
        "",
        "| Nguồn | Mẫu test | FP | FN | Lỗi ≥90% tự tin | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for source, values in by_source.items():
        lines.append(
            f"| {source} | {values['metrics']['row_count']} | {values['false_positives']} | "
            f"{values['false_negatives']} | {values['high_confidence_errors_gte_0_90']} | "
            f"{values['metrics']['f1_label_1']:.3f} |"
        )
    twitter_error_count = sum(
        item["source_dataset"] == "twitter_bot_detection" for item in errors
    )
    short_error_count = theme_counts["short_or_low_context"]
    lines.extend([
        "",
        "## Phát hiện chính",
        "",
        f"- `twitter_bot_detection` tạo {twitter_error_count}/{len(errors)} lỗi "
        f"({twitter_error_count / len(errors):.1%}); đây là nguồn gây lỗi chính.",
        f"- {short_error_count}/{len(errors)} lỗi ({short_error_count / len(errors):.1%}) "
        "là văn bản tối đa 12 tokens, nên text-only model thiếu ngữ cảnh để phân biệt.",
        "- Một số false negatives trong nhóm `phishing` chứa đoạn tiểu thuyết hoặc nội dung không giống phishing; "
        "điều này là dấu hiệu label noise/semantics không đồng nhất của nguồn. Raw label phải được giữ nguyên và chỉ ghi cờ review, không sửa theo cảm tính.",
        "- `fake_profile_post` không có lỗi trên split này dù không còn nhóm trùng chéo; khả năng cao dataset chứa template/pattern riêng rất dễ nhận ra. "
        "Kết quả này không được suy rộng thành khả năng phát hiện tài khoản giả ngoài thực tế.",
    ])
    lines.extend([
        "",
        "## Nhóm dấu hiệu trong các lỗi",
        "",
        "Một lỗi có thể thuộc nhiều nhóm; đây là mô tả để review, không phải nhãn mới.",
        "",
        "| Nhóm | Số lỗi |",
        "| --- | ---: |",
    ])
    for name, count in theme_counts.most_common():
        lines.append(f"| {name} | {count} |")
    lines.extend([
        "",
        "## Các lỗi tự tin cao cần xem trước",
        "",
    ])
    for item in errors[:15]:
        toward_one = ", ".join(value["token"] for value in item["token_evidence"]["toward_label_1"]) or "—"
        toward_zero = ", ".join(value["token"] for value in item["token_evidence"]["toward_label_0"]) or "—"
        lines.extend([
            f"### {item['record_id']} — {item['error_type']} ({item['prediction_confidence']:.1%})",
            "",
            f"- Nguồn: `{item['source_dataset']}`; actual `{item['actual_label']}`, predicted `{item['predicted_label']}`.",
            f"- Từ đẩy về label 1: {toward_one}.",
            f"- Từ đẩy về label 0: {toward_zero}.",
            f"- Preview đã ẩn định danh: {item['redacted_text_preview']}",
            "",
        ])
    lines.extend([
        "## Diễn giải và quyết định",
        "",
        "- Lỗi tự tin cao cho thấy calibration chưa đáng tin; xác suất hiện tại không nên hiển thị như xác suất một vụ lừa đảo thực.",
        "- Chênh lệch lớn theo nguồn cho thấy model học phong cách/dataset pattern. Nâng thuật toán đơn thuần sẽ không giải quyết ground-truth và source shift.",
        "- Bước kế tiếp phù hợp là tạo một baseline text mạnh hơn trên cùng group split, rồi so sánh bằng đúng test cố định; curated/external data vẫn là cổng đánh giá cuối.",
        "",
    ])
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "test_rows": len(rows),
        "total_errors": len(errors),
        "error_type_counts": report["error_type_counts"],
        "high_confidence_errors_gte_0_90": report["high_confidence_errors_gte_0_90"],
        "theme_counts_nonexclusive": report["theme_counts_nonexclusive"],
        "outputs": {"json": str(args.output_json), "markdown": str(args.output_md)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
