"""Extract offline lexical domain features from Crimson URL artifacts.

This script performs no DNS lookup, HTTP request, WHOIS query or page fetch.
It emits unlabeled feature records; Crimson alone is not suitable for binary
classifier training because it does not provide a trustworthy negative class.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


FEATURE_VERSION = "CRIMSON_URL_LEXICAL_V1"
VOWELS = set("aeiou")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def longest_run(value: str, predicate) -> int:
    longest = current = 0
    for character in value:
        if predicate(character):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def is_ip_literal(domain: str) -> bool:
    try:
        ipaddress.ip_address(domain)
        return True
    except ValueError:
        return False


def extract_features(domain: str) -> dict[str, int | float | bool]:
    domain = domain.strip().lower().rstrip(".")
    labels = domain.split(".") if domain else []
    compact = domain.replace(".", "")
    letters = [character for character in compact if character.isalpha()]
    digits = [character for character in compact if character.isdigit()]
    hyphen_count = compact.count("-")
    alnum_sequence = [character for character in compact if character.isalnum()]
    transitions = sum(
        left.isdigit() != right.isdigit()
        for left, right in zip(alnum_sequence, alnum_sequence[1:])
    )
    longest_label = max((len(label) for label in labels), default=0)
    mean_label = statistics.mean(map(len, labels)) if labels else 0.0
    hex_characters = sum(character in "0123456789abcdef" for character in compact)
    return {
        "domain_length": len(domain),
        "label_count": len(labels),
        "subdomain_depth_naive": max(0, len(labels) - 2),
        "rightmost_label_length": len(labels[-1]) if labels else 0,
        "longest_label_length": longest_label,
        "mean_label_length": round(mean_label, 6),
        "letter_count": len(letters),
        "digit_count": len(digits),
        "hyphen_count": hyphen_count,
        "non_ascii_count": sum(ord(character) > 127 for character in domain),
        "digit_ratio": round(len(digits) / len(compact), 6) if compact else 0.0,
        "hyphen_ratio": round(hyphen_count / len(compact), 6) if compact else 0.0,
        "vowel_ratio_among_letters": round(
            sum(character in VOWELS for character in letters) / len(letters), 6
        ) if letters else 0.0,
        "unique_character_ratio": round(len(set(compact)) / len(compact), 6) if compact else 0.0,
        "shannon_entropy": round(shannon_entropy(compact), 6),
        "digit_letter_transition_count": transitions,
        "longest_digit_run": longest_run(compact, str.isdigit),
        "longest_letter_run": longest_run(compact, str.isalpha),
        "punycode_label_count": sum(label.startswith("xn--") for label in labels),
        "is_ip_literal": is_ip_literal(domain),
        "is_ascii": domain.isascii(),
        "rightmost_label_is_numeric": bool(labels and labels[-1].isdigit()),
        "hex_character_ratio": round(hex_characters / len(compact), 6) if compact else 0.0,
    }


def quantiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {}

    def percentile(fraction: float) -> float:
        position = (len(ordered) - 1) * fraction
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return float(ordered[lower])
        return float(ordered[lower] * (upper - position) + ordered[upper] * (position - lower))

    return {
        "min": round(float(ordered[0]), 6),
        "p25": round(percentile(0.25), 6),
        "median": round(percentile(0.50), 6),
        "p75": round(percentile(0.75), 6),
        "p95": round(percentile(0.95), 6),
        "max": round(float(ordered[-1]), 6),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    artifact_ids = set()
    domains = set()
    numeric_values: dict[str, list[float]] = {}
    boolean_counts = Counter()
    with args.input.open(encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8", newline="\n"
    ) as destination:
        for line_number, line in enumerate(source, start=1):
            artifact = json.loads(line)
            artifact_id = artifact.get("artifact_id")
            domain = artifact.get("domain")
            if artifact.get("source_id") != "crimson_www_2025":
                raise ValueError(f"line {line_number}: unexpected source_id")
            if not isinstance(artifact_id, str) or artifact_id in artifact_ids:
                raise ValueError(f"line {line_number}: invalid or duplicate artifact_id")
            if not isinstance(domain, str) or not domain or domain in domains:
                raise ValueError(f"line {line_number}: invalid or duplicate domain")
            features = extract_features(domain)
            record = {
                "artifact_id": artifact_id,
                "source_id": artifact["source_id"],
                "domain": domain,
                "feature_version": FEATURE_VERSION,
                "features": features,
            }
            destination.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            total += 1
            artifact_ids.add(artifact_id)
            domains.add(domain)
            for name, value in features.items():
                if isinstance(value, bool):
                    boolean_counts[name] += int(value)
                else:
                    numeric_values.setdefault(name, []).append(float(value))

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": FEATURE_VERSION,
        "input": str(args.input),
        "input_sha256": sha256_file(args.input),
        "output": str(args.output),
        "output_sha256": sha256_file(args.output),
        "record_count": total,
        "unique_artifact_id_count": len(artifact_ids),
        "unique_domain_count": len(domains),
        "numeric_feature_summary": {
            name: quantiles(values) for name, values in sorted(numeric_values.items())
        },
        "boolean_true_counts": dict(sorted(boolean_counts.items())),
        "network_operations": 0,
        "label_fields_in_output": [],
        "excluded_raw_fields": ["btc", "countryCode", "eth", "ioc", "isp", "query", "region"],
        "rightmost_label_note": "Rightmost label is a lexical component only; no public-suffix inference is claimed.",
        "training_gate": "Do not train a binary classifier until an independently sourced legitimate comparison class and leakage-safe split are available.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "record_count": total,
        "unique_domain_count": len(domains),
        "feature_version": FEATURE_VERSION,
        "network_operations": 0,
        "label_fields_in_output": [],
        "output": str(args.output),
        "report": str(args.report),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
