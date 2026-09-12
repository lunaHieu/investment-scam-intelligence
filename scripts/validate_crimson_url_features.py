"""Validate Crimson lexical URL feature JSONL and its no-label contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from extract_crimson_url_features import FEATURE_VERSION, extract_features


FORBIDDEN_KEYS = {
    "label", "source_label", "ground_truth_status", "ioc", "query", "btc", "eth",
    "countryCode", "country_code", "isp", "region",
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    count = 0
    artifacts = set()
    domains = set()
    with args.input.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = json.loads(line)
            if FORBIDDEN_KEYS.intersection(record) or FORBIDDEN_KEYS.intersection(record.get("features", {})):
                raise ValueError(f"line {line_number}: forbidden label or collection field")
            if record.get("feature_version") != FEATURE_VERSION:
                raise ValueError(f"line {line_number}: wrong feature version")
            artifact_id = record.get("artifact_id")
            domain = record.get("domain")
            if artifact_id in artifacts or domain in domains:
                raise ValueError(f"line {line_number}: duplicate artifact or domain")
            if record.get("features") != extract_features(domain):
                raise ValueError(f"line {line_number}: feature recomputation mismatch")
            artifacts.add(artifact_id)
            domains.add(domain)
            count += 1
    if not count:
        raise ValueError("feature file is empty")
    print(f"VALID: {count} unlabeled Crimson URL feature records; recomputation matched; no forbidden fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
