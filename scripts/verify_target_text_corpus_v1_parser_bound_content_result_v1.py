"""Independently verify parser-bound content results without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
    ROOT,
    verify as verify_release,
)


DEFAULT_RESULT = (
    ROOT
    / "registry"
    / "analyses"
    / "target_text_corpus_v1_parser_bound_content_result_v1.json"
)
LOCAL_QA = (
    ROOT
    / "registry"
    / "analyses"
    / "target_text_corpus_v1_parser_bound_content_release_local_qa_v1.json"
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OUTCOMES = {
    "SUCCESS",
    "PARSER_REJECTED",
    "HTTP_ERROR",
    "TRANSPORT_ERROR",
    "SKIPPED_AFTER_FAILURE",
}
RAW_FIELD_NAMES = {
    "body",
    "raw",
    "raw_body",
    "response_body",
    "response_text",
    "content_base64",
    "payload_base64",
}
PARSER_FIELDS = {
    "GITHUB_COMMIT_METADATA_V1": {
        "required":{"sha", "tree_sha", "parent_shas"},
        "allowed":{"sha", "html_url", "author_date", "committer_date", "tree_sha", "parent_shas"},
    },
    "GITHUB_TREE_METADATA_V1": {
        "required":{"sha", "truncated", "entries"},
        "allowed":{"sha", "truncated", "entries"},
    },
    "NEXVISION_RELEASE_MANIFEST_V1": {
        "required":{"files"},
        "allowed":{"release_version", "generated_at", "files"},
    },
    "NEXVISION_CHECKSUMS_V1": {
        "required":{"entries"},
        "allowed":{"entries"},
    },
    "PDF_SCAMBENCH_METHODS_V1": {
        "required":{"status", "sha256", "bytes"},
        "allowed":{"status", "sha256", "bytes", "page_count", "sections", "rendered_page_count", "render_integrity_status", "visual_review_status", "temporary_artifacts_deleted"},
    },
    "HF_DATASET_REPOSITORY_METADATA_V1": {
        "required":{"id", "sha", "sibling_paths"},
        "allowed":{"id", "sha", "lastModified", "private", "gated", "disabled", "tags", "license", "sibling_paths"},
    },
    "MARKDOWN_DOCUMENTATION_V1": {
        "required":{"sections"},
        "allowed":{"sections"},
    },
    "HF_COMMIT_METADATA_V1": {
        "required":{"commits"},
        "allowed":{"commits"},
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(nested_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(nested_keys(child))
    return keys


def _verify_structured_output(resource: dict, output: Any) -> None:
    if not isinstance(output, dict):
        raise ValueError(f"Structured output is not an object: {resource['resource_id']}")
    contract = PARSER_FIELDS[resource["parser"]]
    actual = set(output)
    if not contract["required"].issubset(actual):
        raise ValueError(f"Required parser fields missing: {resource['resource_id']}")
    if not actual.issubset(contract["allowed"]):
        raise ValueError(f"Non-allowlisted parser fields retained: {resource['resource_id']}")
    if nested_keys(output).intersection(RAW_FIELD_NAMES):
        raise ValueError(f"Raw response field retained: {resource['resource_id']}")
    if resource["resource_id"] in {"PBC06", "PBC08"}:
        forbidden = {key.lower() for key in resource["forbidden_keys"]}
        if nested_keys(output).intersection(forbidden):
            raise ValueError(f"Dataset-like field retained: {resource['resource_id']}")
    if resource["resource_id"] == "PBC02" and output["truncated"] is not False:
        raise ValueError("Truncated GitHub tree cannot be accepted")
    if resource["resource_id"] == "PBC05":
        if output["status"] not in {
            "PDF_VALIDATED_PENDING_BUNDLED_BACKEND_AND_VISUAL_REVIEW",
            "PDF_EXTRACTED_VISUAL_REVIEW_PENDING",
        }:
            raise ValueError("PDF visual-review gate was bypassed")
        if not HEX64.fullmatch(str(output["sha256"])):
            raise ValueError("Invalid PDF hash")
        if output["status"] == "PDF_EXTRACTED_VISUAL_REVIEW_PENDING":
            required = {"page_count", "sections", "rendered_page_count", "render_integrity_status", "visual_review_status", "temporary_artifacts_deleted"}
            if not required.issubset(output):
                raise ValueError("PDF lifecycle result is incomplete")
            if not isinstance(output["page_count"], int) or not 1 <= output["page_count"] <= resource["maximum_pages"]:
                raise ValueError("PDF lifecycle page count invalid")
            if output["rendered_page_count"] != output["page_count"]:
                raise ValueError("PDF rendered page count mismatch")
            if output["render_integrity_status"] != "PASS_PNG_STRUCTURE_AND_PAGE_COUNT":
                raise ValueError("PDF render integrity did not pass")
            if output["visual_review_status"] != "PENDING_REQUIRED":
                raise ValueError("PDF visual review was silently accepted")
            if output["temporary_artifacts_deleted"] is not True:
                raise ValueError("PDF temporary artifacts were retained")
            if not isinstance(output["sections"], list):
                raise ValueError("PDF extracted sections must be a list")
            for section in output["sections"]:
                if set(section) != {"page", "matched_terms", "text"}:
                    raise ValueError("PDF extracted section schema changed")
    if resource["resource_id"] == "PBC07":
        if not isinstance(output["sections"], dict):
            raise ValueError("Markdown sections must be an object")
        if not set(output["sections"]).issubset(set(resource["retained_sections"])):
            raise ValueError("Unexpected Markdown section retained")


def verify_result(path: Path = DEFAULT_RESULT) -> dict:
    release_check = verify_release(require_absent=False)
    if release_check["status"] != "PASS_LOCAL_PARSER_BOUND_RELEASE_VERIFIED_EXECUTION_CLOSED":
        raise ValueError("Release verification failed")
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    result = json.loads(path.read_text(encoding="utf-8"))

    inputs = {item["role"]:item for item in result["inputs"]}
    if inputs["release"]["path"] != str(RELEASE.relative_to(ROOT)).replace("\\", "/"):
        raise ValueError("Result release path mismatch")
    if inputs["release"]["sha256"] != sha256_file(RELEASE):
        raise ValueError("Result release hash mismatch")
    if inputs["release_qa"]["path"] != str(LOCAL_QA.relative_to(ROOT)).replace("\\", "/"):
        raise ValueError("Result release-QA path mismatch")
    if inputs["release_qa"]["sha256"] != sha256_file(LOCAL_QA):
        raise ValueError("Result release-QA hash mismatch")

    expected = release["resources"]
    rows = result["resources"]
    if [row["resource_id"] for row in rows] != [item["resource_id"] for item in expected]:
        raise ValueError("Resource order or identity changed")
    if len(rows) != len(expected):
        raise ValueError("Resource cardinality changed")

    total_bytes = 0
    failure_seen = False
    for resource, row in zip(expected, rows):
        for key in ("source_endpoint_id", "url", "parser"):
            if row[key] != resource[key]:
                raise ValueError(f"Resource lineage mismatch: {resource['resource_id']}:{key}")
        if row["outcome"] not in OUTCOMES:
            raise ValueError(f"Unknown outcome: {row['outcome']}")
        if failure_seen and row["outcome"] != "SKIPPED_AFTER_FAILURE":
            raise ValueError(f"Resource continued after earlier failure: {resource['resource_id']}")
        if row.get("raw_response_retained") is not False:
            raise ValueError(f"Raw response retained: {resource['resource_id']}")
        if nested_keys(row).intersection(RAW_FIELD_NAMES):
            raise ValueError(f"Raw response field present: {resource['resource_id']}")

        response_bytes = row.get("response_bytes", 0)
        if not isinstance(response_bytes, int) or response_bytes < 0:
            raise ValueError(f"Invalid byte count: {resource['resource_id']}")
        if response_bytes > resource["maximum_bytes"]:
            bounded_oversize_probe = (
                row["outcome"] == "PARSER_REJECTED"
                and row.get("diagnostic_code") == "BYTE_CEILING_EXCEEDED"
                and response_bytes == resource["maximum_bytes"] + 1
            )
            if not bounded_oversize_probe:
                raise ValueError(f"Resource byte ceiling exceeded: {resource['resource_id']}")
        total_bytes += response_bytes

        if row["outcome"] == "SKIPPED_AFTER_FAILURE":
            if any(row.get(key) is not None for key in (
                "final_url", "http_status", "content_type", "response_sha256",
                "structured_output",
            )) or response_bytes != 0:
                raise ValueError(f"Skipped resource contains response data: {resource['resource_id']}")
            if row.get("diagnostic_code") != "EARLIER_RESOURCE_FAILED":
                raise ValueError(f"Skipped resource diagnostic mismatch: {resource['resource_id']}")
        elif row["outcome"] == "SUCCESS":
            if row.get("diagnostic_code") is not None:
                raise ValueError(f"Successful resource retained a diagnostic: {resource['resource_id']}")
            if row.get("http_status") != 200:
                raise ValueError(f"Successful resource lacks HTTP 200: {resource['resource_id']}")
            if not HEX64.fullmatch(str(row.get("response_sha256", ""))):
                raise ValueError(f"Successful resource lacks response hash: {resource['resource_id']}")
            content_type = str(row.get("content_type", "")).split(";", 1)[0].lower()
            if content_type not in resource["content_types"]:
                raise ValueError(f"Content type mismatch: {resource['resource_id']}")
            final_url = row.get("final_url")
            if not isinstance(final_url, str):
                raise ValueError(f"Final URL missing: {resource['resource_id']}")
            if resource["resource_id"] == "PBC07":
                if resource["required_final_url_contains"] not in final_url:
                    raise ValueError("Immutable Markdown redirect identity missing")
            elif final_url != resource["url"]:
                raise ValueError(f"Unexpected redirect: {resource['resource_id']}")
            if urlparse(final_url).hostname not in {"api.github.com", "raw.githubusercontent.com", "aclanthology.org", "huggingface.co"}:
                raise ValueError(f"Final authority not allowed: {resource['resource_id']}")
            _verify_structured_output(resource, row.get("structured_output"))
            if resource["resource_id"] == "PBC05":
                pdf = row["structured_output"]
                if pdf["sha256"] != row["response_sha256"] or pdf["bytes"] != response_bytes:
                    raise ValueError("PDF structured output does not match response identity")
        else:
            if row.get("structured_output") is not None:
                raise ValueError(f"Failed resource retained structured output: {resource['resource_id']}")
            if not isinstance(row.get("diagnostic_code"), str) or not row["diagnostic_code"]:
                raise ValueError(f"Failed resource lacks diagnostic code: {resource['resource_id']}")
            if row["outcome"] == "HTTP_ERROR":
                if not isinstance(row.get("http_status"), int) or row["http_status"] == 200:
                    raise ValueError(f"HTTP error status invalid: {resource['resource_id']}")
                if not isinstance(row.get("final_url"), str):
                    raise ValueError(f"HTTP error final URL missing: {resource['resource_id']}")
                if not HEX64.fullmatch(str(row.get("response_sha256", ""))):
                    raise ValueError(f"HTTP error response hash missing: {resource['resource_id']}")
            elif row["outcome"] == "TRANSPORT_ERROR":
                if any(row.get(key) is not None for key in (
                    "final_url", "http_status", "content_type", "response_sha256",
                )) or response_bytes != 0:
                    raise ValueError(f"Transport error retained response metadata: {resource['resource_id']}")
            elif row["outcome"] == "PARSER_REJECTED":
                if row.get("http_status") != 200:
                    raise ValueError(f"Parser rejection lacks HTTP 200: {resource['resource_id']}")
                if not isinstance(row.get("final_url"), str):
                    raise ValueError(f"Parser rejection final URL missing: {resource['resource_id']}")
                if not HEX64.fullmatch(str(row.get("response_sha256", ""))):
                    raise ValueError(f"Parser rejection response hash missing: {resource['resource_id']}")
        if row["outcome"] not in {"SUCCESS", "SKIPPED_AFTER_FAILURE"}:
            failure_seen = True

    if total_bytes > release["execution_contract"]["maximum_total_response_bytes"]:
        raise ValueError("Aggregate byte ceiling exceeded")
    counts = Counter(row["outcome"] for row in rows)
    expected_summary = {
        "resources":len(rows),
        "success":counts["SUCCESS"],
        "parser_rejected":counts["PARSER_REJECTED"],
        "http_error":counts["HTTP_ERROR"],
        "transport_error":counts["TRANSPORT_ERROR"],
        "skipped_after_failure":counts["SKIPPED_AFTER_FAILURE"],
        "response_bytes":total_bytes,
    }
    for key, value in expected_summary.items():
        if result["summary"][key] != value:
            raise ValueError(f"Summary mismatch: {key}")

    safety = result["safety_contract"]
    for key in (
        "raw_responses_retained",
        "dataset_files_downloaded",
        "candidate_domain_access_operations",
        "labels_created",
        "validation_or_test_rows_opened",
        "model_operations",
    ):
        if safety[key] != 0:
            raise ValueError(f"Forbidden side effect recorded: {key}")
    if safety["training_allowed"] is not False:
        raise ValueError("Training gate opened")
    decision = result["decision"]
    if decision["dataset_acquisition_allowed"] is not False or decision["training_allowed"] is not False:
        raise ValueError("Downstream data or training gate opened")
    if decision["evidence_acceptance_allowed"] is not False:
        raise ValueError("Evidence accepted before PDF visual review")

    return {
        "status":"PASS_PARSER_BOUND_CONTENT_RESULT_VERIFIED",
        **expected_summary,
        "evidence_acceptance_allowed":False,
        "dataset_acquisition_allowed":False,
        "training_allowed":False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    print(json.dumps(verify_result(args.result), ensure_ascii=False))


if __name__ == "__main__":
    main()
