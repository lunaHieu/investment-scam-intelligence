"""Validate the evidence-only UBCKNN seed without third-party dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "registry" / "pilots" / "ubcknn_warning_seed_2026-09-08.json"


def assert_schema_shape(item: dict, schema_name: str) -> None:
    """Check the V1 contract surface used by this dependency-free pilot validator."""
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    required = set(schema["required"])
    allowed = set(schema["properties"])
    missing = required - set(item)
    unknown = set(item) - allowed
    if missing:
        raise ValueError(f"{schema_name}: missing required fields {sorted(missing)}")
    if unknown:
        raise ValueError(f"{schema_name}: unknown fields {sorted(unknown)}")


def main() -> None:
    data = json.loads(PILOT.read_text(encoding="utf-8"))
    cases = data["cases"]
    evidence = data["evidence"]
    artifacts = data["warning_artifacts"]
    for case in cases:
        assert_schema_shape(case, "case.schema.json")
    for item in evidence:
        assert_schema_shape(item, "evidence.schema.json")
    for artifact in artifacts:
        assert_schema_shape(artifact, "artifact.schema.json")
    case_ids = {case["case_id"] for case in cases}
    if len(case_ids) != len(cases):
        raise ValueError("Duplicate case_id in UBCKNN pilot")
    if {item["case_id"] for item in evidence} != case_ids:
        raise ValueError("Each UBCKNN pilot case must have exactly one evidence record")
    artifact_ids = {artifact["artifact_id"] for artifact in artifacts}
    if len(artifact_ids) != len(artifacts) or len(artifact_ids) != len(cases):
        raise ValueError("Each UBCKNN pilot case must have one distinct warning artifact")
    if {item["artifact_id"] for item in evidence} != artifact_ids:
        raise ValueError("Evidence must link to its warning artifact")
    if any(item["source_id"] != "ubcknn_warnings" for item in evidence):
        raise ValueError("UBCKNN pilot may contain only UBCKNN evidence")
    if any(urlparse(item["source_url"]).netloc != "ssc.gov.vn" for item in evidence):
        raise ValueError("UBCKNN pilot evidence must point to ssc.gov.vn")
    if any(case["review_status"] != "REVIEWED" for case in cases):
        raise ValueError("Pilot cases must be manually reviewed")
    if any(case["ground_truth_status"] != "UNCERTAIN" for case in cases):
        raise ValueError("A single UBCKNN warning cannot confirm a case in this pilot")
    if any(artifact["artifact_type"] != "WARNING_DOCUMENT" for artifact in artifacts):
        raise ValueError("Pilot artifacts must remain warning documents")
    if any(artifact["has_text"] or artifact["has_image"] for artifact in artifacts):
        raise ValueError("Warning documents must not become model-content artifacts")
    print(
        f"UBCKNN pilot valid: {len(cases)} UNCERTAIN cases, "
        f"{len(evidence)} official-warning records and {len(artifacts)} provenance artifacts."
    )


if __name__ == "__main__":
    main()
