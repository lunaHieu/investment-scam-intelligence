"""Extract transparent Financial Claims V1 signals from the Mendeley group split.

This is a deterministic candidate-signal extractor, not a scam classifier.  It
processes only train and validation rows; the frozen test partition is skipped.
No source labels, source identities, metadata, or review fields are emitted as
predictive features.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


FEATURE_VERSION = "MENDELEY_FINANCIAL_CLAIMS_V1"
ALLOWED_PARTITIONS = frozenset({"train", "validation"})
SIGNAL_TYPES = (
    "RETURN_RATE",
    "RETURN_MULTIPLE",
    "MONEY_AMOUNT",
    "GUARANTEED_RETURN",
    "NO_RISK",
    "URGENCY_SCARCITY",
    "PASSIVE_OR_EASY_INCOME",
    "RECRUITMENT_REWARD",
    "PAYMENT_OR_TRANSFER_REQUEST",
    "ADVANCE_FEE_OR_WITHDRAWAL",
    "CRYPTO_INVESTMENT_OR_PAYMENT",
)


PERCENT = r"(?:\d{1,4}(?:[.,]\d{1,2})?\s*(?:%|percent\b|per\s+cent\b|phần\s+trăm\b))"
RETURN_CUE = (
    r"(?:returns?|profits?|gains?|roi|yield|interest\s+rate|income|earn(?:ed|ing|ings|s)?|"
    r"payouts?|lợi\s+nhuận|sinh\s+lời|thu\s+nhập|kiếm\s+được)"
)
CURRENCY_AMOUNT = (
    r"(?:[$€£¥₫]\s*\d[\d,.]*(?:\s*[kmb])?|"
    r"\b\d[\d,.]*(?:\s*[kmb])?\s*(?:usd|usdt|eur|gbp|vnd|btc|eth|dollars?|đồng)\b)"
)
PAYMENT_ASSET = r"(?:money|funds?|cash|crypto|bitcoin|ethereum|usdt|wallet|bank\s+account|tiền|ví)"
INVESTMENT_ASSET_CUE = r"(?:crypto(?:currency)?|bitcoin|ethereum|btc|eth|usdt|tokens?|coins?|altcoins?|stocks?)"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    signal_type: str
    pattern: re.Pattern[str]
    description: str


def compile_rule(rule_id: str, signal_type: str, pattern: str, description: str) -> Rule:
    return Rule(rule_id, signal_type, re.compile(pattern, re.IGNORECASE | re.UNICODE), description)


RULES = (
    compile_rule(
        "FC_RETURN_RATE_01",
        "RETURN_RATE",
        rf"(?:{RETURN_CUE}.{{0,60}}?{PERCENT}|{PERCENT}.{{0,60}}?{RETURN_CUE})",
        "A percentage appears near a return, profit, yield, or income cue.",
    ),
    compile_rule(
        "FC_RETURN_MULTIPLE_01",
        "RETURN_MULTIPLE",
        r"(?:\b(?:double|triple|multiply)\b.{0,45}\b(?:money|investment|returns?|profits?)\b|"
        r"\b\d+(?:[.,]\d+)?\s*x\b.{0,45}\b(?:returns?|profits?|gains?|money)\b|"
        r"\b(?:returns?|profits?|gains?|money)\b.{0,45}\b\d+(?:[.,]\d+)?\s*x\b|"
        rf"\b{INVESTMENT_ASSET_CUE}\b.{{0,45}}\b\d+(?:[.,]\d+)?\s*x\b|"
        rf"\b\d+(?:[.,]\d+)?\s*x\b.{{0,45}}\b{INVESTMENT_ASSET_CUE}\b|"
        r"(?:nhân\s+(?:đôi|ba)|gấp\s+\d+(?:[.,]\d+)?\s*lần).{0,45}(?:tiền|lợi\s+nhuận|đầu\s+tư))",
        "The text claims that money, profit, or return will multiply.",
    ),
    compile_rule(
        "FC_MONEY_AMOUNT_01",
        "MONEY_AMOUNT",
        CURRENCY_AMOUNT,
        "An explicit currency-denominated amount appears in the text.",
    ),
    compile_rule(
        "FC_GUARANTEE_01",
        "GUARANTEED_RETURN",
        rf"(?:\b(?:guaranteed?|assured?|certain)\b.{{0,45}}?{RETURN_CUE}|"
        rf"{RETURN_CUE}.{{0,45}}?\b(?:guaranteed?|assured?|certain)\b|"
        r"(?:cam\s+kết|đảm\s+bảo|chắc\s+chắn).{0,45}(?:lợi\s+nhuận|sinh\s+lời|thu\s+nhập|kiếm\s+tiền))",
        "A return, profit, or income outcome is described as guaranteed or certain.",
    ),
    compile_rule(
        "FC_NO_RISK_01",
        "NO_RISK",
        r"(?:\brisk[ -]?free\b|\b(?:no|zero|without|little\s+or\s+no)\s+risk\b|"
        r"\b100\s*%\s+safe\b|\b(?:can(?:not|'t)|never)\s+lose\b|"
        r"không\s+(?:có\s+)?rủi\s+ro|an\s+toàn\s+tuyệt\s+đối|không\s+thể\s+thua\s+lỗ)",
        "The opportunity is framed as risk-free, completely safe, or impossible to lose.",
    ),
    compile_rule(
        "FC_URGENCY_01",
        "URGENCY_SCARCITY",
        r"(?:\b(?:act|invest\w*|buy|join|register|sign\s+up)\s+(?:right\s+)?now\b|"
        r"\blimited\s+(?:time|offer|spots?|slots?|availability)\b|\b(?:last|final)\s+chance\b|"
        r"\btoday\s+only\b|\bbefore\s+it(?:'s|\s+is)\s+too\s+late\b|"
        r"\bdon'?t\s+miss(?:\s+out)?\b|\burgent(?:\s+(?:offer|opportunity|proposal|investment|action|response|business))?\b|"
        r"\b(?:act|invest\w*|buy|join|register|sign\s+up|send|transfer|deposit|pay)\s+immediately\b|"
        r"đầu\s+tư\s+ngay|tham\s+gia\s+ngay|cơ\s+hội\s+cuối|đừng\s+bỏ\s+lỡ|"
        r"số\s+lượng\s+có\s+hạn|chỉ\s+hôm\s+nay|khẩn\s+cấp)",
        "The text pressures the reader to act quickly or invokes scarcity.",
    ),
    compile_rule(
        "FC_EASY_INCOME_01",
        "PASSIVE_OR_EASY_INCOME",
        r"(?:\bpassive\s+income\b|\beasy\s+money\b|\bquick\s+money\b|\bget\s+rich\s+quick\b|"
        r"\bfinancial\s+freedom\b|\bquit\s+your\s+(?:day\s+)?job\b|"
        r"\bwork\s+from\s+home\b.{0,45}\b(?:earn|income|money)\b|"
        r"thu\s+nhập\s+thụ\s+động|làm\s+giàu\s+nhanh|kiếm\s+tiền\s+dễ\s+dàng|tự\s+do\s+tài\s+chính)",
        "Income is framed as passive, easy, fast, or sufficient to quit a job.",
    ),
    compile_rule(
        "FC_RECRUITMENT_01",
        "RECRUITMENT_REWARD",
        r"(?:\b(?:referral|recruit(?:ing|ment|ed|s)?|invite(?:d|s)?|downline)\b.{0,55}\b(?:bonus|commission|income|reward|profit)\w*\b|"
        r"\b(?:bonus|commission|income|reward|profit)\w*\b.{0,55}\b(?:referral|recruit(?:ing|ment|ed|s)?|invite(?:d|s)?|downline)\b|"
        r"(?:giới\s+thiệu|tuyển|mời).{0,55}(?:hoa\s+hồng|thưởng|thu\s+nhập|lợi\s+nhuận))",
        "Recruitment or referral activity is connected to a reward or income.",
    ),
    compile_rule(
        "FC_PAYMENT_01",
        "PAYMENT_OR_TRANSFER_REQUEST",
        rf"(?:\b(?:please|kindly|must|need\s+to|required\s+to|you(?:'ll|\s+will)?\s+need\s+to)\b.{{0,45}}"
        rf"\b(?:send|transfer|deposit|pay|wire|fund)\w*\b.{{0,50}}?{PAYMENT_ASSET}|"
        rf"\b(?:send|transfer|deposit|wire)\w*\b.{{0,45}}?(?:crypto|bitcoin|ethereum|usdt|wallet|bank\s+account)|"
        r"(?:gửi|chuyển|nạp|thanh\s+toán).{0,50}(?:tiền|crypto|bitcoin|usdt|ví|tài\s+khoản))",
        "The reader is asked or instructed to send, transfer, deposit, or pay assets.",
    ),
    compile_rule(
        "FC_ADVANCE_FEE_01",
        "ADVANCE_FEE_OR_WITHDRAWAL",
        r"(?:\b(?:pay|send|transfer|required?)\w*\b.{0,30}\b(?:fee|tax|charge)\b.{0,50}\b(?:withdraw|release|unlock)\w*\b|"
        r"\b(?:withdraw|release|unlock)\w*\b.{0,30}\b(?:funds?|money|account|payment)\b.{0,50}\b(?:fee|tax|charge)\b|"
        r"\bwithdrawal\s+(?:processing\s+)?fee\b|"
        r"(?:phí|thuế).{0,55}(?:rút|mở\s+khóa|giải\s+ngân)|"
        r"(?:rút|mở\s+khóa|giải\s+ngân).{0,55}(?:phí|thuế))",
        "A fee, tax, or charge is connected to withdrawing, releasing, or unlocking funds.",
    ),
    compile_rule(
        "FC_CRYPTO_01",
        "CRYPTO_INVESTMENT_OR_PAYMENT",
        r"(?:\b(?:crypto(?:currency)?|bitcoin|ethereum|btc|eth|usdt|token)\b.{0,65}"
        r"\b(?:invest|send|transfer|deposit|pay|returns?|profits?|earn)\w*\b|"
        r"\b(?:invest|send|transfer|deposit|pay|returns?|profits?|earn)\w*\b.{0,65}"
        r"\b(?:crypto(?:currency)?|bitcoin|ethereum|btc|eth|usdt|token)\b|"
        rf"\b{INVESTMENT_ASSET_CUE}\b.{{0,45}}\b\d+(?:[.,]\d+)?\s*x\b|"
        rf"\b\d+(?:[.,]\d+)?\s*x\b.{{0,45}}\b{INVESTMENT_ASSET_CUE}\b|"
        r"(?:đầu\s+tư|gửi|chuyển|nạp|lợi\s+nhuận).{0,65}(?:tiền\s+mã\s+hóa|bitcoin|ethereum|usdt))",
        "Cryptocurrency is connected to investing, payment, transfer, or returns.",
    ),
)


PERCENT_VALUE = re.compile(r"(?i)(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:%|percent\b|per\s+cent\b|phần\s+trăm\b)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_context(text: str, start: int, end: int, radius: int = 70) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    context = re.sub(r"\s+", " ", text[left:right]).strip()
    if left:
        context = "…" + context
    if right < len(text):
        context += "…"
    return context


def compact_excerpt(text: str, limit: int = 320) -> str:
    excerpt = re.sub(r"\s+", " ", text).strip()
    return excerpt if len(excerpt) <= limit else excerpt[:limit].rstrip() + "…"


def extract_signals(text: str) -> tuple[list[dict[str, object]], dict[str, int | float | bool]]:
    matches: list[dict[str, object]] = []
    seen: set[tuple[str, int, int]] = set()
    for rule in RULES:
        for match in rule.pattern.finditer(text):
            key = (rule.signal_type, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            matched_text = re.sub(r"\s+", " ", match.group(0)).strip()
            matches.append(
                {
                    "rule_id": rule.rule_id,
                    "signal_type": rule.signal_type,
                    "start": match.start(),
                    "end": match.end(),
                    "matched_text": matched_text,
                    "context": compact_context(text, match.start(), match.end()),
                }
            )
    matches.sort(key=lambda item: (item["start"], item["end"], item["rule_id"]))
    signal_counts = Counter(str(item["signal_type"]) for item in matches)
    percentages: list[float] = []
    for item in matches:
        if item["signal_type"] != "RETURN_RATE":
            continue
        for value in PERCENT_VALUE.findall(str(item["matched_text"])):
            try:
                percentages.append(float(value.replace(",", ".")))
            except ValueError:
                continue
    features: dict[str, int | float | bool] = {
        "signal_match_count": len(matches),
        "signal_type_count": len(signal_counts),
        "return_percentage_count": len(percentages),
        "max_return_percentage": max(percentages, default=0.0),
    }
    for signal_type in SIGNAL_TYPES:
        name = signal_type.lower()
        features[f"has_{name}"] = signal_counts[signal_type] > 0
        features[f"{name}_count"] = signal_counts[signal_type]
    return matches, features


def deterministic_key(record_id: str, salt: str) -> str:
    return hashlib.sha256(f"{FEATURE_VERSION}|{salt}|{record_id}".encode()).hexdigest()


def rule_set_sha256() -> str:
    payload = [
        {
            "rule_id": rule.rule_id,
            "signal_type": rule.signal_type,
            "pattern": rule.pattern.pattern,
            "description": rule.description,
        }
        for rule in RULES
    ]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def select_review_queue(
    records: list[dict[str, object]], candidate_target: int = 80, no_signal_target: int = 40
) -> list[dict[str, object]]:
    buckets: dict[str, list[dict[str, object]]] = {}
    for signal_type in SIGNAL_TYPES:
        bucket = [record for record in records if signal_type in record["signal_types"]]
        buckets[signal_type] = sorted(
            bucket, key=lambda record: deterministic_key(str(record["record_id"]), signal_type)
        )

    selected: list[dict[str, object]] = []
    selected_records: set[str] = set()
    selected_groups: set[str] = set()
    positions = {signal_type: 0 for signal_type in SIGNAL_TYPES}
    while len(selected) < candidate_target:
        added = False
        for signal_type in SIGNAL_TYPES:
            bucket = buckets[signal_type]
            while positions[signal_type] < len(bucket):
                record = bucket[positions[signal_type]]
                positions[signal_type] += 1
                record_id = str(record["record_id"])
                group_id = str(record["split_group_id"])
                if record_id in selected_records or group_id in selected_groups:
                    continue
                selected.append({**record, "queue_reason": "SIGNAL_CANDIDATE", "review_status": "UNREVIEWED"})
                selected_records.add(record_id)
                selected_groups.add(group_id)
                added = True
                break
            if len(selected) >= candidate_target:
                break
        if not added:
            break

    no_signal = sorted(
        (record for record in records if not record["signal_types"]),
        key=lambda record: deterministic_key(str(record["record_id"]), "NO_SIGNAL_AUDIT"),
    )
    for record in no_signal:
        if len(selected) >= candidate_target + no_signal_target:
            break
        record_id = str(record["record_id"])
        group_id = str(record["split_group_id"])
        if record_id in selected_records or group_id in selected_groups:
            continue
        selected.append({**record, "queue_reason": "NO_SIGNAL_AUDIT", "review_status": "UNREVIEWED"})
        selected_records.add(record_id)
        selected_groups.add(group_id)
    return selected


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--review-queue", type=Path, required=True)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.review_queue.parent.mkdir(parents=True, exist_ok=True)
    total_input = 0
    processed_counts: Counter[str] = Counter()
    skipped_counts: Counter[str] = Counter()
    signal_record_counts: Counter[str] = Counter()
    signal_match_counts: Counter[str] = Counter()
    candidate_records = 0
    record_ids: set[str] = set()
    groups_by_partition: dict[str, set[str]] = defaultdict(set)
    review_source: list[dict[str, object]] = []

    with args.input.open("r", encoding="utf-8-sig", newline="") as source, args.output.open(
        "w", encoding="utf-8", newline="\n"
    ) as destination:
        reader = csv.DictReader(source)
        required = {"record_id", "text_content", "partition", "split_group_id"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Input is missing required columns: {sorted(required)}")
        for row_number, row in enumerate(reader, start=2):
            total_input += 1
            partition = (row.get("partition") or "").strip().lower()
            if partition not in ALLOWED_PARTITIONS:
                skipped_counts[partition or "<MISSING>"] += 1
                continue
            record_id = (row.get("record_id") or "").strip()
            group_id = (row.get("split_group_id") or "").strip()
            if not record_id or record_id in record_ids:
                raise ValueError(f"row {row_number}: missing or duplicate record_id")
            if not group_id:
                raise ValueError(f"row {row_number}: missing split_group_id")
            text = row.get("text_content") or ""
            signals, features = extract_signals(text)
            signal_types = sorted({str(item["signal_type"]) for item in signals})
            output_record = {
                "record_id": record_id,
                "partition": partition,
                "split_group_id": group_id,
                "feature_version": FEATURE_VERSION,
                "signal_types": signal_types,
                "signals": signals,
                "features": features,
            }
            destination.write(json.dumps(output_record, ensure_ascii=False, separators=(",", ":")) + "\n")
            record_ids.add(record_id)
            groups_by_partition[partition].add(group_id)
            processed_counts[partition] += 1
            if signals:
                candidate_records += 1
            for signal_type in signal_types:
                signal_record_counts[signal_type] += 1
            for signal in signals:
                signal_match_counts[str(signal["signal_type"])] += 1
            review_source.append(
                {
                    "record_id": record_id,
                    "partition": partition,
                    "split_group_id": group_id,
                    "signal_types": signal_types,
                    "text_excerpt": compact_excerpt(text),
                    "evidence_contexts": [str(signal["context"]) for signal in signals[:5]],
                }
            )

    queue = select_review_queue(review_source)
    with args.review_queue.open("w", encoding="utf-8", newline="\n") as destination:
        for item in queue:
            destination.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    queue_reasons = Counter(str(item["queue_reason"]) for item in queue)
    queue_signal_types: Counter[str] = Counter()
    for item in queue:
        for signal_type in item["signal_types"]:
            queue_signal_types[str(signal_type)] += 1
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": FEATURE_VERSION,
        "input": str(args.input),
        "input_sha256": sha256_file(args.input),
        "included_partitions": sorted(ALLOWED_PARTITIONS),
        "total_input_record_count": total_input,
        "processed_record_count": sum(processed_counts.values()),
        "processed_partition_counts": dict(sorted(processed_counts.items())),
        "processed_unique_group_counts": {
            partition: len(groups) for partition, groups in sorted(groups_by_partition.items())
        },
        "skipped_partition_counts": dict(sorted(skipped_counts.items())),
        "test_partition_text_processed": 0,
        "candidate_record_count": candidate_records,
        "candidate_record_ratio": round(candidate_records / max(1, sum(processed_counts.values())), 6),
        "signal_record_counts": {name: signal_record_counts[name] for name in SIGNAL_TYPES},
        "signal_match_counts": {name: signal_match_counts[name] for name in SIGNAL_TYPES},
        "rule_count": len(RULES),
        "rule_set_sha256": rule_set_sha256(),
        "rules": [
            {
                "rule_id": rule.rule_id,
                "signal_type": rule.signal_type,
                "description": rule.description,
            }
            for rule in RULES
        ],
        "output": str(args.output),
        "output_sha256": sha256_file(args.output),
        "review_queue": str(args.review_queue),
        "review_queue_sha256": sha256_file(args.review_queue),
        "review_queue_record_count": len(queue),
        "review_queue_reason_counts": dict(sorted(queue_reasons.items())),
        "review_queue_signal_type_counts": {
            name: queue_signal_types[name] for name in SIGNAL_TYPES
        },
        "review_queue_unique_group_count": len({str(item["split_group_id"]) for item in queue}),
        "source_labels_used_for_extraction": False,
        "source_labels_emitted": False,
        "network_operations": 0,
        "raw_files_modified": False,
        "interpretation": (
            "Signals are deterministic lexical candidates with evidence spans. They are not scam labels, "
            "risk probabilities, or verified financial claims."
        ),
        "training_gate": (
            "Do not use these features for model training until the review queue has been independently "
            "annotated and rule precision/coverage have been documented."
        ),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "feature_version": FEATURE_VERSION,
                "processed_record_count": report["processed_record_count"],
                "test_partition_text_processed": 0,
                "candidate_record_count": candidate_records,
                "review_queue_record_count": len(queue),
                "output": str(args.output),
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
