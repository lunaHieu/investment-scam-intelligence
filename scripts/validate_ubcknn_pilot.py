"""Validate the evidence-only UBCKNN seed without third-party dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "registry" / "pilots" / "ubcknn_warning_seed_2026-09-08.json"


def main() -> None:
    data = json.loads(PILOT.read_text(encoding="utf-8"))
    cases = data["cases"]
    evidence = data["evidence"]
    case_ids = {case["case_id"] for case in cases}
    if len(case_ids) != len(cases):
        raise ValueError("Duplicate case_id in UBCKNN pilot")
    if {item["case_id"] for item in evidence} != case_ids:
        raise ValueError("Each UBCKNN pilot case must have exactly one evidence record")
    if any(item["source_id"] != "ubcknn_warnings" for item in evidence):
        raise ValueError("UBCKNN pilot may contain only UBCKNN evidence")
    if any(urlparse(item["source_url"]).netloc != "ssc.gov.vn" for item in evidence):
        raise ValueError("UBCKNN pilot evidence must point to ssc.gov.vn")
    if any(case["review_status"] != "REVIEWED" for case in cases):
        raise ValueError("Pilot cases must be manually reviewed")
    print(f"UBCKNN pilot valid: {len(cases)} cases, {len(evidence)} official-warning records.")


if __name__ == "__main__":
    main()
