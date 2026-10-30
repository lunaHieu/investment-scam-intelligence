"""Independently verify exact PBC05/PBC08 diagnostic result metadata."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_diagnostic_release_v1 import ROOT, RELEASE


DEFAULT_RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.json"
QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_diagnostic_release_qa_v1.json"
PASS_STATUS = "PASS_PARSER_BOUND_DIAGNOSTIC_RESULT_VERIFIED"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OUTCOMES = {"SUCCESS", "PARSER_REJECTED", "HTTP_ERROR", "TRANSPORT_ERROR", "SKIPPED_AFTER_FAILURE"}
PBC05_CODES = {
    "PDF_LIFECYCLE_PDF_INVALID_MAGIC", "PDF_LIFECYCLE_PDF_OPEN_OR_PARSE_ERROR",
    "PDF_LIFECYCLE_PDF_PAGE_LIMIT_EXCEEDED", "PDF_LIFECYCLE_PDF_PAGE_TEXT_EXTRACTION_ERROR",
    "PDF_LIFECYCLE_PDF_EXTRACTION_RUNTIME_ERROR", "PDF_LIFECYCLE_RUNTIME_ERROR",
    "PDF_LIFECYCLE_PDFINFO_NONZERO", "PDF_LIFECYCLE_SECTION_EXTRACTION_NONZERO",
    "PDF_LIFECYCLE_PDFTOPPM_RENDER_NONZERO", "PDF_LIFECYCLE_PDFINFO_LAUNCH_ERROR",
    "PDF_LIFECYCLE_SECTION_EXTRACTION_LAUNCH_ERROR", "PDF_LIFECYCLE_PDFTOPPM_RENDER_LAUNCH_ERROR",
}
PBC08_CODES = {
    "PARSER_REJECTED_FORBIDDEN_DATASET_KEY_PRESENT",
    "PARSER_REJECTED_COMMIT_LIST_MISSING_OR_INVALID",
    "PARSER_REJECTED_COMMIT_ENTRY_NOT_OBJECT",
    "PARSER_REJECTED_COMMIT_ID_INVALID",
    "PARSER_REJECTED_VALUEERROR",
    "PARSER_REJECTED_TYPEERROR",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_result(path: Path = DEFAULT_RESULT) -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    resource_contracts = {row["resource_id"]: row for row in release["resources"]}
    result = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if result.get("result_id") != "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_RESULT_V1":
        errors.append("Result identity changed")
    inputs = {item.get("role"): item for item in result.get("inputs", [])}
    expected = {"diagnostic_release": RELEASE, "release_qa": QA}
    if set(inputs) != set(expected):
        errors.append("Result input roles changed")
    for role, source in expected.items():
        if not source.is_file() or inputs.get(role, {}).get("sha256") != sha256_file(source):
            errors.append(f"Pinned result input mismatch: {role}")
    rows = result.get("resources", [])
    if [row.get("resource_id") for row in rows] != ["PBC05", "PBC08"]:
        errors.append("Result row order/population changed")
    provider_failure = False
    for row in rows:
        rid = row.get("resource_id")
        if row.get("outcome") not in OUTCOMES:
            errors.append(f"Unknown result outcome: {rid}")
            continue
        if row.get("raw_response_retained") is not False:
            errors.append(f"Raw response retained: {rid}")
        if not isinstance(row.get("response_bytes"), int) or row["response_bytes"] < 0:
            errors.append(f"Invalid response size: {rid}")
        contract = resource_contracts.get(rid, {})
        if row.get("response_bytes", 0) > contract.get("maximum_bytes", -1):
            errors.append(f"Response exceeds byte ceiling: {rid}")
        if row.get("url") != contract.get("url"):
            errors.append(f"Request URL changed: {rid}")
        if row.get("http_status") is not None:
            media_type = str(row.get("content_type") or "").split(";", 1)[0].strip().lower()
            if media_type not in contract.get("content_types", []):
                errors.append(f"Content type outside allowlist: {rid}")
        if row.get("final_url") is not None and row.get("final_url") != contract.get("url"):
            errors.append(f"Redirect/final URL changed: {rid}")
        outcome = row["outcome"]
        if outcome == "SUCCESS":
            if row.get("http_status") != 200 or not HEX64.fullmatch(str(row.get("response_sha256", ""))):
                errors.append(f"Success identity invalid: {rid}")
            if row.get("structured_output") is None:
                errors.append(f"Success output missing: {rid}")
        elif outcome == "PARSER_REJECTED":
            if row.get("http_status") != 200 or not HEX64.fullmatch(str(row.get("response_sha256", ""))):
                errors.append(f"Parser-rejection identity invalid: {rid}")
            if row.get("structured_output") is not None:
                errors.append(f"Rejected row retained structured output: {rid}")
            code = str(row.get("diagnostic_code", ""))
            allowed = PBC05_CODES if rid == "PBC05" else PBC08_CODES
            if code not in allowed:
                errors.append(f"Diagnostic code outside allowlist: {rid}")
            if rid == "PBC05" and row.get("diagnostic_details") is not None:
                details = row["diagnostic_details"]
                allowed_keys = {"stage", "returncode", "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256"}
                if set(details) != allowed_keys or not HEX64.fullmatch(str(details.get("stderr_sha256", ""))):
                    errors.append("PBC05 retained diagnostics are not hash-only")
        elif outcome == "HTTP_ERROR":
            if row.get("http_status") in (None, 200):
                errors.append(f"Invalid HTTP error status: {rid}")
            provider_failure = True
        elif outcome == "TRANSPORT_ERROR":
            if row.get("response_bytes") != 0 or any(row.get(k) is not None for k in ("http_status", "response_sha256", "content_type", "final_url")):
                errors.append(f"Transport row retained response data: {rid}")
            provider_failure = True
        elif outcome == "SKIPPED_AFTER_FAILURE":
            if not provider_failure or row.get("response_bytes") != 0:
                errors.append("Skipped row lacks prior provider failure")
    counts = Counter(row.get("outcome") for row in rows)
    expected_summary = {
        "resources": 2,
        "success": counts["SUCCESS"],
        "parser_rejected": counts["PARSER_REJECTED"],
        "http_error": counts["HTTP_ERROR"],
        "transport_error": counts["TRANSPORT_ERROR"],
        "skipped_after_failure": counts["SKIPPED_AFTER_FAILURE"],
        "response_bytes": sum(row.get("response_bytes", 0) for row in rows),
    }
    if result.get("summary") != expected_summary:
        errors.append("Summary mismatch")
    safety = result.get("safety_contract", {})
    if any(safety.get(key) != 0 for key in ("raw_responses_retained", "dataset_files_downloaded", "candidate_domain_access_operations", "labels_created", "validation_or_test_rows_opened", "model_operations")):
        errors.append("Forbidden side effect recorded")
    if any(result.get("decision", {}).get(key) is not False for key in ("evidence_acceptance_allowed", "dataset_acquisition_allowed", "training_allowed")):
        errors.append("Downstream decision gate opened")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_RESULT_VERIFICATION_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "result": {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)},
        "checks": {**expected_summary, "network_operations_during_verification": 0},
        "decision": {"result_verified": not errors, "evidence_acceptance_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "raw_artifacts_retained": 0, "labels_created": 0, "model_operations": 0},
    }


if __name__ == "__main__":
    print(json.dumps(verify_result(), ensure_ascii=False, indent=2))
