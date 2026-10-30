"""Independently verify exact PBC05-PBC08 supplemental parser-bound results."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE as V1_RELEASE, ROOT


RELEASE = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_supplemental_release_v1.json"
QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_supplemental_release_qa_v1.json"
DEFAULT_RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_supplemental_result_v1.json"
PASS_STATUS = "PASS_PARSER_BOUND_SUPPLEMENTAL_RESULT_VERIFIED"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OUTCOMES = {"SUCCESS", "PARSER_REJECTED", "HTTP_ERROR", "TRANSPORT_ERROR", "SKIPPED_AFTER_FAILURE"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_result(path: Path = DEFAULT_RESULT) -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    v1 = json.loads(V1_RELEASE.read_text(encoding="utf-8"))
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("result_id") != "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_SUPPLEMENTAL_RESULT_V1":
        raise ValueError("Supplemental result identity changed")
    inputs = {item["role"]: item for item in result.get("inputs", [])}
    expected_inputs = {
        "supplemental_release": (RELEASE, sha256_file(RELEASE)),
        "supplemental_release_qa": (QA, sha256_file(QA)),
        "immutable_v1_result": (
            ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_result_v1.json",
            release["inputs"][0]["sha256"],
        ),
    }
    if set(inputs) != set(expected_inputs):
        raise ValueError("Supplemental result inputs changed")
    for role, (source, digest) in expected_inputs.items():
        if inputs[role].get("sha256") != digest or not source.is_file():
            raise ValueError(f"Supplemental input mismatch: {role}")

    resources_by_id = {item["resource_id"]: item for item in v1["resources"]}
    expected_ids = release["resource_ids"]
    rows = result.get("resources", [])
    if [row.get("resource_id") for row in rows] != expected_ids:
        raise ValueError("Supplemental result population or order changed")
    provider_failure_seen = False
    total_bytes = 0
    for row in rows:
        resource = resources_by_id[row["resource_id"]]
        outcome = row.get("outcome")
        if outcome not in OUTCOMES:
            raise ValueError(f"Unknown supplemental outcome: {outcome}")
        if row.get("raw_response_retained") is not False:
            raise ValueError("Supplemental row retained a raw response")
        response_bytes = row.get("response_bytes")
        if not isinstance(response_bytes, int) or response_bytes < 0 or response_bytes > resource["maximum_bytes"]:
            raise ValueError("Supplemental response byte count invalid")
        total_bytes += response_bytes
        if provider_failure_seen:
            if outcome != "SKIPPED_AFTER_FAILURE" or response_bytes != 0:
                raise ValueError("Row after provider failure was not skipped")
            if row.get("diagnostic_code") != "EARLIER_PROVIDER_OR_TRANSPORT_FAILURE":
                raise ValueError("Skipped-row diagnostic changed")
            continue
        if outcome == "SUCCESS":
            if row.get("http_status") != 200 or not HEX64.fullmatch(str(row.get("response_sha256", ""))):
                raise ValueError("Successful supplemental row lacks response identity")
            if row.get("diagnostic_code") is not None or row.get("diagnostic_details") is not None:
                raise ValueError("Successful supplemental row retained diagnostics")
            if row.get("structured_output") is None:
                raise ValueError("Successful supplemental row lacks structured output")
            if row["resource_id"] == "PBC05":
                output = row["structured_output"]
                if output.get("visual_review_status") != "PENDING_REQUIRED" or output.get("temporary_artifacts_deleted") is not True:
                    raise ValueError("PBC05 visual-review or cleanup gate changed")
                if output.get("sha256") != row["response_sha256"] or output.get("bytes") != response_bytes:
                    raise ValueError("PBC05 structured identity mismatch")
        elif outcome == "PARSER_REJECTED":
            if row.get("http_status") != 200 or not HEX64.fullmatch(str(row.get("response_sha256", ""))):
                raise ValueError("Parser rejection lacks response identity")
            if row.get("structured_output") is not None or not row.get("diagnostic_code"):
                raise ValueError("Parser rejection schema invalid")
            details = row.get("diagnostic_details")
            if row["resource_id"] == "PBC05" and details is not None:
                allowed = {"stage", "returncode", "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256"}
                if set(details) != allowed or details["stage"] not in {"PDFINFO", "SECTION_EXTRACTION", "PDFTOPPM_RENDER"}:
                    raise ValueError("PBC05 diagnostic details changed")
                if not HEX64.fullmatch(str(details["stdout_sha256"])) or not HEX64.fullmatch(str(details["stderr_sha256"])):
                    raise ValueError("PBC05 diagnostic hashes invalid")
        elif outcome == "HTTP_ERROR":
            if row.get("http_status") in {None, 200}:
                raise ValueError("HTTP error status invalid")
            provider_failure_seen = True
        elif outcome == "TRANSPORT_ERROR":
            if response_bytes != 0 or any(row.get(key) is not None for key in ("http_status", "response_sha256", "content_type", "final_url")):
                raise ValueError("Transport error retained response metadata")
            provider_failure_seen = True
        else:
            raise ValueError("Unexpected skipped row before provider failure")

    counts = Counter(row["outcome"] for row in rows)
    expected_summary = {
        "resources": 4,
        "success": counts["SUCCESS"],
        "parser_rejected": counts["PARSER_REJECTED"],
        "http_error": counts["HTTP_ERROR"],
        "transport_error": counts["TRANSPORT_ERROR"],
        "skipped_after_failure": counts["SKIPPED_AFTER_FAILURE"],
        "response_bytes": total_bytes,
    }
    if result.get("summary") != expected_summary:
        raise ValueError("Supplemental summary mismatch")
    safety = result.get("safety_contract", {})
    for key in ("raw_responses_retained", "dataset_files_downloaded", "candidate_domain_access_operations", "labels_created", "validation_or_test_rows_opened", "model_operations"):
        if safety.get(key) != 0:
            raise ValueError(f"Forbidden supplemental side effect: {key}")
    decision = result.get("decision", {})
    if any(decision.get(key) is not False for key in ("evidence_acceptance_allowed", "dataset_acquisition_allowed", "training_allowed")):
        raise ValueError("Supplemental result opened a downstream gate")
    return {"status": PASS_STATUS, **expected_summary, "training_allowed": False}


if __name__ == "__main__":
    print(json.dumps(verify_result(), ensure_ascii=False, indent=2))
