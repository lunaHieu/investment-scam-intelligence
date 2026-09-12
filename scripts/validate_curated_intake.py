"""Validate a small manual curated-intake batch without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


STATUSES = {"CONFIRMED", "LEGITIMATE", "UNCERTAIN"}
CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
REVIEW = {"UNREVIEWED", "IN_REVIEW", "REVIEWED", "RECONCILED"}
EVIDENCE_TYPES = {
    "regulator_warning", "enforcement_record", "court_record", "official_registry",
    "consumer_complaint", "domain_lookup", "web_snapshot", "payment_signal", "cross_check",
}


def is_url(value: object) -> bool:
    parsed = urlparse(value) if isinstance(value, str) else None
    return bool(parsed and parsed.scheme in {"http", "https"} and parsed.netloc)


def validate(batch: dict) -> list[str]:
    errors: list[str] = []
    records = batch.get("records")
    if not isinstance(records, list) or not records:
        return ["records must be a non-empty list"]
    if len(records) > 20:
        errors.append("pilot allows at most 20 records")

    seen_case_ids, seen_artifact_ids, seen_evidence_ids = set(), set(), set()
    for index, record in enumerate(records, start=1):
        prefix = f"records[{index}]"
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not re.fullmatch(r"CASE_[A-Z0-9_-]+", case_id):
            errors.append(f"{prefix}.case_id must match CASE_[A-Z0-9_-]+")
        elif case_id in seen_case_ids:
            errors.append(f"{prefix}.case_id is duplicated")
        else:
            seen_case_ids.add(case_id)
        if record.get("ground_truth_status") not in STATUSES:
            errors.append(f"{prefix}.ground_truth_status is invalid")
        if record.get("label_confidence") not in CONFIDENCE:
            errors.append(f"{prefix}.label_confidence is invalid")
        if record.get("review_status") not in REVIEW:
            errors.append(f"{prefix}.review_status is invalid")

        artifact = record.get("artifact")
        if not isinstance(artifact, dict):
            errors.append(f"{prefix}.artifact must be an object")
        else:
            artifact_id = artifact.get("artifact_id")
            if not isinstance(artifact_id, str) or not re.fullmatch(r"ART_[A-Z0-9_-]+", artifact_id):
                errors.append(f"{prefix}.artifact.artifact_id is invalid")
            elif artifact_id in seen_artifact_ids:
                errors.append(f"{prefix}.artifact.artifact_id is duplicated")
            else:
                seen_artifact_ids.add(artifact_id)
            for flag in ("has_text", "has_image", "has_url"):
                if not isinstance(artifact.get(flag), bool):
                    errors.append(f"{prefix}.artifact.{flag} must be boolean")
            if artifact.get("has_url") and not is_url(artifact.get("url")):
                errors.append(f"{prefix}.artifact.url must be a valid HTTP(S) URL when has_url is true")

        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix}.evidence must contain at least one item")
        else:
            for evidence_index, item in enumerate(evidence, start=1):
                eprefix = f"{prefix}.evidence[{evidence_index}]"
                evidence_id = item.get("evidence_id") if isinstance(item, dict) else None
                if not isinstance(evidence_id, str) or not re.fullmatch(r"EVD_[A-Z0-9_-]+", evidence_id):
                    errors.append(f"{eprefix}.evidence_id is invalid")
                elif evidence_id in seen_evidence_ids:
                    errors.append(f"{eprefix}.evidence_id is duplicated")
                else:
                    seen_evidence_ids.add(evidence_id)
                if not isinstance(item, dict) or item.get("evidence_type") not in EVIDENCE_TYPES:
                    errors.append(f"{eprefix}.evidence_type is invalid")
                elif not is_url(item.get("source_url")):
                    errors.append(f"{eprefix}.source_url must be a valid HTTP(S) URL")

        if record.get("ground_truth_status") == "CONFIRMED":
            types = {item.get("evidence_type") for item in evidence if isinstance(item, dict)} if isinstance(evidence, list) else set()
            strong = {"enforcement_record", "court_record", "regulator_warning", "cross_check"}
            if not types.intersection(strong):
                errors.append(f"{prefix}: CONFIRMED needs independent corroboration, not only a consumer complaint or registry reference")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read intake batch: {exc}", file=sys.stderr)
        return 2
    errors = validate(data)
    if errors:
        print("INVALID")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"VALID: {len(data['records'])} records ready for human review; no model-training export was created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
