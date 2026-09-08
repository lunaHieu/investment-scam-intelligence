"""Validate a URL-only candidate artifact JSONL file without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    args = parser.parse_args()
    total = 0
    artifact_ids: set[str] = set()
    domains: set[str] = set()
    with args.input.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            artifact = json.loads(line)
            total += 1
            required = {
                "artifact_id", "case_id", "source_id", "source_record_id", "artifact_type",
                "collection_date", "has_text", "has_image", "has_url",
            }
            if missing := required - set(artifact):
                raise ValueError(f"line {line_number}: missing {sorted(missing)}")
            if artifact["artifact_id"] in artifact_ids:
                raise ValueError(f"line {line_number}: duplicate artifact_id")
            artifact_ids.add(artifact["artifact_id"])
            if artifact["source_id"] != args.source_id or artifact["case_id"] is not None:
                raise ValueError(f"line {line_number}: wrong source or non-null case_id")
            if artifact["artifact_type"] != "URL" or artifact["has_text"] or artifact["has_image"] or not artifact["has_url"]:
                raise ValueError(f"line {line_number}: candidate must remain URL-only")
            parsed = urlparse(artifact["url"])
            if parsed.scheme != "https" or not parsed.hostname or artifact["domain"] != parsed.hostname.lower():
                raise ValueError(f"line {line_number}: invalid canonical URL/domain")
            domains.add(artifact["domain"])
    if not total:
        raise ValueError("candidate file is empty")
    print(f"Candidate artifacts valid: {total} URL-only artifacts, {len(domains)} domains.")


if __name__ == "__main__":
    main()
