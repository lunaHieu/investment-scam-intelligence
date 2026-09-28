"""Validate a provenance-preserving external text evaluation intake batch.

This command is offline. It verifies local capture files and hashes, checks the
frozen evidence/review policy, and reports readiness. It never opens source
URLs, scores a model, creates labels, or modifies raw captures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


POLICY_ID = "ISI_TEXT_BASELINE_V2_EXTERNAL_EVAL_POLICY_V1"
ALLOWED_BATCH_STATUSES = {"TEMPLATE_ONLY", "DRAFT", "IN_REVIEW", "RECONCILED"}
ALLOWED_GROUND_TRUTH = {"CONFIRMED", "LEGITIMATE", "UNCERTAIN"}
ALLOWED_ARTIFACT_TYPES = {"POST", "MESSAGE", "WEBSITE_SNAPSHOT"}
ALLOWED_EVIDENCE_TYPES = {
    "regulator_warning",
    "enforcement_record",
    "court_record",
    "official_registry",
    "consumer_complaint",
    "domain_lookup",
    "web_snapshot",
    "payment_signal",
    "cross_check",
}
ALLOWED_SUPPORTS = {
    "IDENTITY",
    "SCAM_CLAIM",
    "LEGITIMACY",
    "DOMAIN_LINK",
    "PAYMENT_SIGNAL",
    "CAMPAIGN_LINK",
}
CONFIRMED_STRONG_EVIDENCE = {
    "regulator_warning",
    "enforcement_record",
    "court_record",
    "cross_check",
}
LEGITIMATE_STRONG_EVIDENCE = {
    "official_registry",
    "enforcement_record",
    "court_record",
    "cross_check",
}
MINIMUM_NON_WHITESPACE_TEXT = 20
MINIMUM_TOTAL = 20
MINIMUM_CONFIRMED = 10
MINIMUM_LEGITIMATE = 10
ID_PATTERNS = {
    "case_id": re.compile(r"^CASE_[A-Z0-9_-]+$"),
    "artifact_id": re.compile(r"^ART_[A-Z0-9_-]+$"),
    "evidence_id": re.compile(r"^EVD_[A-Z0-9_-]+$"),
    "case_or_campaign_group_id": re.compile(r"^(?:CASEGRP|CAMPAIGN)_[A-Z0-9_-]+$"),
    "near_duplicate_group_id": re.compile(r"^NDG_[A-Z0-9_-]+$"),
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def is_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def non_whitespace_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def valid_id(field: str, value: object) -> bool:
    return isinstance(value, str) and bool(ID_PATTERNS[field].fullmatch(value))


def resolve_capture_path(raw_root: Path, relative_value: object) -> tuple[Path | None, str | None]:
    if not isinstance(relative_value, str) or not relative_value.strip():
        return None, "source_capture_path must be a non-empty path relative to raw_root"
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        return None, "source_capture_path must stay within raw_root"
    root = raw_root.resolve()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        return None, "source_capture_path resolves outside raw_root"
    return resolved, None


def reviewed_supporting_evidence(record: dict, support: str) -> list[dict]:
    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        return []
    return [
        item
        for item in evidence
        if isinstance(item, dict)
        and item.get("reviewed") is True
        and support in item.get("supports", [])
    ]


def record_eligibility(record: dict, capture_valid: bool) -> tuple[bool, list[str]]:
    reasons = []
    status = record.get("ground_truth_status")
    if status not in {"CONFIRMED", "LEGITIMATE"}:
        reasons.append("ground_truth_status_not_confirmed_or_legitimate")
    if record.get("label_confidence") != "HIGH":
        reasons.append("label_confidence_not_high")
    if record.get("review_status") != "RECONCILED":
        reasons.append("review_status_not_reconciled")
    artifact = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
    if artifact.get("artifact_type") not in ALLOWED_ARTIFACT_TYPES:
        reasons.append("artifact_type_not_model_eligible")
    text = artifact.get("text")
    if not isinstance(text, str) or non_whitespace_length(text) < MINIMUM_NON_WHITESPACE_TEXT:
        reasons.append("observed_text_too_short_or_missing")
    if not capture_valid:
        reasons.append("source_capture_missing_or_hash_invalid")
    if not valid_id("case_or_campaign_group_id", record.get("case_or_campaign_group_id")):
        reasons.append("case_or_campaign_group_missing")
    if not valid_id("near_duplicate_group_id", record.get("near_duplicate_group_id")):
        reasons.append("near_duplicate_group_missing")
    required_support = {
        "CONFIRMED": "SCAM_CLAIM",
        "LEGITIMATE": "LEGITIMACY",
    }.get(status)
    if required_support is not None:
        supporting = reviewed_supporting_evidence(record, required_support)
        if not supporting:
            reasons.append(f"no_reviewed_{required_support.lower()}_evidence")
        elif status == "CONFIRMED" and not any(
            item.get("evidence_type") in CONFIRMED_STRONG_EVIDENCE for item in supporting
        ):
            reasons.append("confirmed_case_lacks_independent_strong_evidence")
        elif status == "LEGITIMATE" and not any(
            item.get("evidence_type") in LEGITIMATE_STRONG_EVIDENCE for item in supporting
        ):
            reasons.append("legitimate_case_lacks_official_strong_evidence")
    return not reasons, reasons


def validate_batch(batch: dict, raw_root: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    if batch.get("policy_id") != POLICY_ID:
        errors.append(f"policy_id must equal {POLICY_ID}")
    status = batch.get("status")
    if status not in ALLOWED_BATCH_STATUSES:
        errors.append(f"status must be one of {sorted(ALLOWED_BATCH_STATUSES)}")
    batch_id = batch.get("batch_id")
    if not isinstance(batch_id, str) or not re.fullmatch(r"[A-Z0-9_-]+", batch_id):
        errors.append("batch_id must contain only uppercase letters, digits, underscore, or hyphen")
    source_scope = batch.get("source_scope")
    if not isinstance(source_scope, list) or any(
        not isinstance(item, str) or not item for item in source_scope
    ):
        errors.append("source_scope must be a list of non-empty source IDs")
    records = batch.get("records")
    if not isinstance(records, list):
        return errors + ["records must be a list"], {
            "record_count": 0,
            "eligible_count": 0,
            "reporting_allowed": False,
        }
    if status == "TEMPLATE_ONLY" and records:
        errors.append("TEMPLATE_ONLY batch must not contain records")
    if status != "TEMPLATE_ONLY" and not records:
        errors.append("non-template batch must contain at least one record")

    seen = {"case_id": set(), "artifact_id": set(), "evidence_id": set()}
    exact_text_groups: dict[str, set[str]] = defaultdict(set)
    case_group_labels: dict[str, set[str]] = defaultdict(set)
    near_duplicate_labels: dict[str, set[str]] = defaultdict(set)
    record_results = []
    capture_hashes = {}

    for index, record in enumerate(records, start=1):
        prefix = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("case_id", "case_or_campaign_group_id", "near_duplicate_group_id"):
            if not valid_id(field, record.get(field)):
                errors.append(f"{prefix}.{field} has an invalid format")
        case_id = record.get("case_id")
        if isinstance(case_id, str):
            if case_id in seen["case_id"]:
                errors.append(f"{prefix}.case_id is duplicated")
            seen["case_id"].add(case_id)
        if record.get("ground_truth_status") not in ALLOWED_GROUND_TRUTH:
            errors.append(f"{prefix}.ground_truth_status is invalid")
        if record.get("label_confidence") not in {"HIGH", "MEDIUM", "LOW"}:
            errors.append(f"{prefix}.label_confidence is invalid")
        if record.get("review_status") not in {
            "UNREVIEWED",
            "IN_REVIEW",
            "REVIEWED",
            "RECONCILED",
        }:
            errors.append(f"{prefix}.review_status is invalid")
        rationale = record.get("review_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{prefix}.review_rationale must be non-empty")

        artifact = record.get("artifact")
        capture_valid = False
        text_hash = None
        if not isinstance(artifact, dict):
            errors.append(f"{prefix}.artifact must be an object")
            artifact = {}
        artifact_id = artifact.get("artifact_id")
        if not valid_id("artifact_id", artifact_id):
            errors.append(f"{prefix}.artifact.artifact_id has an invalid format")
        elif artifact_id in seen["artifact_id"]:
            errors.append(f"{prefix}.artifact.artifact_id is duplicated")
        else:
            seen["artifact_id"].add(artifact_id)
        source_id = artifact.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            errors.append(f"{prefix}.artifact.source_id must be non-empty")
        elif source_id == "mendeley_investment_deceptive_2026":
            errors.append(f"{prefix}.artifact.source_id must be external to Mendeley")
        elif isinstance(source_scope, list) and source_id not in source_scope:
            errors.append(f"{prefix}.artifact.source_id is not listed in source_scope")
        if artifact.get("artifact_type") not in ALLOWED_ARTIFACT_TYPES:
            errors.append(f"{prefix}.artifact.artifact_type is not allowed")
        if not is_url(artifact.get("url")):
            errors.append(f"{prefix}.artifact.url must be a valid HTTP(S) URL")
        text = artifact.get("text")
        if not isinstance(text, str) or non_whitespace_length(text) < MINIMUM_NON_WHITESPACE_TEXT:
            errors.append(
                f"{prefix}.artifact.text must contain at least "
                f"{MINIMUM_NON_WHITESPACE_TEXT} non-whitespace characters"
            )
        else:
            text_hash = sha256_bytes(text.encode("utf-8"))
            if artifact.get("text_sha256") != text_hash:
                errors.append(f"{prefix}.artifact.text_sha256 does not match exact UTF-8 text")
            near_group = record.get("near_duplicate_group_id")
            if isinstance(near_group, str):
                exact_text_groups[text_hash].add(near_group)
        declared_capture_hash = artifact.get("source_capture_sha256")
        if not is_sha256(declared_capture_hash):
            errors.append(f"{prefix}.artifact.source_capture_sha256 is invalid")
        capture_path, path_error = resolve_capture_path(
            raw_root, artifact.get("source_capture_path")
        )
        if path_error:
            errors.append(f"{prefix}.artifact.{path_error}")
        elif capture_path is not None and not capture_path.is_file():
            errors.append(f"{prefix}.artifact source capture does not exist: {capture_path}")
        elif capture_path is not None and is_sha256(declared_capture_hash):
            actual_capture_hash = sha256_file(capture_path)
            capture_hashes[str(capture_path)] = actual_capture_hash
            if actual_capture_hash != declared_capture_hash:
                errors.append(f"{prefix}.artifact.source_capture_sha256 mismatch")
            else:
                capture_valid = True

        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix}.evidence must contain at least one item")
            evidence = []
        for evidence_index, item in enumerate(evidence, start=1):
            eprefix = f"{prefix}.evidence[{evidence_index}]"
            if not isinstance(item, dict):
                errors.append(f"{eprefix} must be an object")
                continue
            evidence_id = item.get("evidence_id")
            if not valid_id("evidence_id", evidence_id):
                errors.append(f"{eprefix}.evidence_id has an invalid format")
            elif evidence_id in seen["evidence_id"]:
                errors.append(f"{eprefix}.evidence_id is duplicated")
            else:
                seen["evidence_id"].add(evidence_id)
            if item.get("evidence_type") not in ALLOWED_EVIDENCE_TYPES:
                errors.append(f"{eprefix}.evidence_type is invalid")
            if not is_url(item.get("source_url")):
                errors.append(f"{eprefix}.source_url must be a valid HTTP(S) URL")
            supports = item.get("supports")
            if not isinstance(supports, list) or any(
                support not in ALLOWED_SUPPORTS for support in supports
            ):
                errors.append(f"{eprefix}.supports contains an invalid value")
            if type(item.get("reviewed")) is not bool:
                errors.append(f"{eprefix}.reviewed must be boolean")
            summary = item.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f"{eprefix}.summary must be non-empty")

        eligible, eligibility_reasons = record_eligibility(record, capture_valid)
        record_results.append(
            {
                "case_id": case_id,
                "ground_truth_status": record.get("ground_truth_status"),
                "eligible": eligible,
                "eligibility_reasons": eligibility_reasons,
                "text_sha256": text_hash,
                "capture_valid": capture_valid,
            }
        )
        case_group = record.get("case_or_campaign_group_id")
        near_group = record.get("near_duplicate_group_id")
        label = record.get("ground_truth_status")
        if isinstance(case_group, str) and isinstance(label, str):
            case_group_labels[case_group].add(label)
        if isinstance(near_group, str) and isinstance(label, str):
            near_duplicate_labels[near_group].add(label)

    for text_hash, groups in sorted(exact_text_groups.items()):
        if len(groups) > 1:
            errors.append(
                f"exact duplicate text {text_hash} spans multiple near_duplicate_group_id values"
            )
    for group, labels in sorted(case_group_labels.items()):
        bounded = labels & {"CONFIRMED", "LEGITIMATE"}
        if len(bounded) > 1:
            errors.append(f"case/campaign group {group} contains conflicting eligible labels")
    for group, labels in sorted(near_duplicate_labels.items()):
        bounded = labels & {"CONFIRMED", "LEGITIMATE"}
        if len(bounded) > 1:
            errors.append(f"near-duplicate group {group} contains conflicting eligible labels")

    eligible = [item for item in record_results if item["eligible"]]
    eligible_counts = Counter(item["ground_truth_status"] for item in eligible)
    reporting_checks = {
        "minimum_total_eligible_records_met": len(eligible) >= MINIMUM_TOTAL,
        "minimum_confirmed_records_met": eligible_counts["CONFIRMED"]
        >= MINIMUM_CONFIRMED,
        "minimum_legitimate_records_met": eligible_counts["LEGITIMATE"]
        >= MINIMUM_LEGITIMATE,
    }
    report = {
        "record_count": len(records),
        "eligible_count": len(eligible),
        "eligible_confirmed": eligible_counts["CONFIRMED"],
        "eligible_legitimate": eligible_counts["LEGITIMATE"],
        "reporting_gate": {
            "minimum_total": MINIMUM_TOTAL,
            "minimum_confirmed": MINIMUM_CONFIRMED,
            "minimum_legitimate": MINIMUM_LEGITIMATE,
            "checks": reporting_checks,
            "reporting_allowed": all(reporting_checks.values()) and not errors,
        },
        "record_results": record_results,
        "capture_file_hashes": capture_hashes,
        "structural_error_count": len(errors),
        "reporting_allowed": all(reporting_checks.values()) and not errors,
    }
    return errors, report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--run-at", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--require-reporting-gate", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(f"Missing intake batch: {args.input}")
    batch = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(batch, dict):
        raise ValueError("Intake batch must be a JSON object")
    errors, report = validate_batch(batch, args.raw_root)
    result = {
        "analysis_id": "ISI_EXTERNAL_TEXT_INTAKE_VALIDATION_V1",
        "run_at": args.run_at or datetime.now(timezone.utc).isoformat(),
        "batch_id": batch.get("batch_id"),
        "batch_status": batch.get("status"),
        "input": str(args.input),
        "input_sha256": sha256_file(args.input),
        "raw_root": str(args.raw_root),
        **report,
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "source_url_access_operations": 0,
            "model_scoring_operations": 0,
            "labels_created": 0,
            "raw_files_modified": False,
        },
    }
    if args.report is not None:
        if args.report.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite report: {args.report}")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        return 1
    if args.require_reporting_gate and not result["reporting_allowed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
