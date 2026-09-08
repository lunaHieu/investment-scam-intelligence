"""Create URL-only candidate artifacts from a pinned Crimson raw file."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.crimson import normalize_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--collection-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    report = normalize_records(args.input, args.output, args.collection_date)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Candidate artifacts: {report['candidate_artifact_count']}")
    print(f"Invalid URLs: {report['invalid_url_count']}")
    print(f"Output: {args.output}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
