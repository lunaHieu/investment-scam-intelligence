"""Verify the frozen one-row ready-channel CDX metadata canary release."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.archive_retry_policy_v1 import decide
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_CANARY_RELEASE_V1"
QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CDX_CANARY_RELEASE_QA_V1"
PASS_STATUS = "PASS_FROZEN_ONE_ROW_READY_CHANNEL_CDX_METADATA_CANARY_RELEASE"
TARGET_ID = "TTCV1_B3_AVAIL_002"
CONTINUATION_QA_STATUS = (
    "PASS_PARTIAL_EXACT_69_CONTINUATION_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED"
)
EXPECTED_FIELDS = ["timestamp", "original", "statuscode", "mimetype", "digest"]
EXPECTED_OUTPUT = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs"
    r"\ready_channel_cdx_canary_result_v1\cdx_canary_report_v1.json"
)


def _resolve(root: Path, item: dict[str, Any]) -> Path:
    path = Path(str(item.get("path", "")))
    return path if item.get("absolute", path.is_absolute()) else root / path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load_object(release_path)
    except Exception as error:
        return {
            "verification_id": QA_ID,
            "status": "FAIL",
            "errors": [f"Release load failed: {type(error).__name__}: {error}"],
        }
    root = release_path.resolve().parents[1]
    if release.get("release_id") != RELEASE_ID:
        errors.append("Unexpected ready-channel CDX canary release identity")
    if release.get("status") != "FROZEN_ONE_ROW_METADATA_CANARY_NOT_BEFORE_GATE":
        errors.append("Unexpected ready-channel CDX canary release status")

    for item in release.get("basis", []):
        path = _resolve(root, item)
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Canary basis hash mismatch: {item.get('role')}")
    paths: dict[str, Path] = {}
    for role, item in release.get("inputs", {}).items():
        path = _resolve(root, item)
        paths[role] = path
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Canary input hash mismatch: {role}")

    try:
        protocol = load_object(paths["fallback_protocol"])
        protocol_qa = load_object(paths["fallback_protocol_qa"])
        continuation = load_object(paths["continuation_report"])
        continuation_qa = load_object(paths["continuation_result_qa"])
        source_rows = _read_jsonl(paths["source_plan"])
    except Exception as error:
        errors.append(f"Canary authoritative input load failed: {type(error).__name__}: {error}")
        protocol = protocol_qa = continuation = continuation_qa = {}
        source_rows = []

    if protocol_qa.get("status") != "PASS_CONDITIONAL_CDX_METADATA_FALLBACK_PREPARED_NETWORK_CLOSED":
        errors.append("Conditional fallback protocol QA is not authoritative PASS")
    if continuation_qa.get("status") != CONTINUATION_QA_STATUS or continuation_qa.get("errors") != []:
        errors.append("Continuation result QA does not authorize conditional fallback activation")
    if continuation.get("status") != "INCOMPLETE_ERRORS_PRESERVED" or continuation.get("stopped_on_http_429") is not True:
        errors.append("Continuation report does not preserve the required HTTP 429 partial result")
    if continuation.get("network_request_count") != 1 or continuation.get("unresolved_error_count") != 69:
        errors.append("Continuation report request/unresolved counts changed")
    results = continuation.get("results", [])
    first = results[0] if isinstance(results, list) and results else {}
    if first.get("availability_plan_id") != TARGET_ID or first.get("snapshot_http_status") != "429":
        errors.append("Continuation trigger result is not the frozen canary row HTTP 429")
    if first.get("response_diagnostics", {}).get("response_headers", {}).get("Retry-After") is not None:
        errors.append("Canary release incorrectly ignores a present Retry-After header")
    if not source_rows or source_rows[1].get("availability_plan_id") != TARGET_ID:
        errors.append("Source plan second row is not the frozen canary identity")

    target = release.get("target_record", {})
    expected_target = {
        key: source_rows[1].get(key) if len(source_rows) > 1 else None
        for key in (
            "availability_plan_id",
            "candidate_id",
            "cohort",
            "channel_id",
            "channel_target_stratum",
            "candidate_host",
            "candidate_url",
            "target_timestamp",
        )
    }
    if target != expected_target:
        errors.append("Frozen canary target identity changed")
    if protocol.get("canary_contract", {}).get("target_availability_plan_id") != TARGET_ID:
        errors.append("Fallback protocol canary identity changed")

    cooldown = release.get("adaptive_gate", {})
    decision = decide(
        failure_class="HTTP_429",
        observed_at=str(continuation.get("created_at")),
        network_attempts=1,
        consecutive_failures=4,
        retry_after=None,
    )
    if cooldown.get("policy_decision") != decision:
        errors.append("Canary adaptive retry decision is not independently reproducible")
    try:
        created = datetime.fromisoformat(str(release.get("created_at")))
        observed = datetime.fromisoformat(str(continuation.get("created_at")))
        not_before = datetime.fromisoformat(str(cooldown.get("not_before")))
        seconds = int((not_before - observed).total_seconds())
        if cooldown.get("not_before") != decision.get("not_before") or seconds != 86400:
            errors.append("Canary adaptive gate differs from the fourth bounded rate-limit step")
        if created < observed or created >= not_before:
            errors.append("Canary release was not prepared inside the offline-only gate window")
    except Exception as error:
        seconds = None
        errors.append(f"Invalid canary timestamps: {type(error).__name__}: {error}")

    contract = release.get("cdx_contract", {})
    query = contract.get("query", {})
    expected_contract = {
        "endpoint": "https://web.archive.org/cdx/search/cdx",
        "allowed_network_hosts": ["web.archive.org"],
        "minimum_delay_seconds": 60.0,
        "maximum_logical_requests": 1,
        "maximum_attempts_per_query": 1,
        "timeout_seconds": 30,
        "maximum_redirects": 0,
        "maximum_response_bytes": 2097152,
        "required_content_type_prefix": "application/json",
        "stop_on_http_429": True,
        "partial_journal_reserved_before_network": True,
        "partial_journal_auto_resume_allowed": False,
        "output_overwrite_allowed": False,
        "archived_page_download_allowed": False,
    }
    for field, value in expected_contract.items():
        if contract.get(field) != value:
            errors.append(f"Canary CDX contract changed: {field}")
    expected_query = {
        "url": f"{target.get('candidate_host', '')}/",
        "matchType": "exact",
        "output": "json",
        "fields": EXPECTED_FIELDS,
        "filters": ["statuscode:200", "mimetype:text/html"],
        "maximum_rows": 1000,
    }
    if query != expected_query:
        errors.append("Canary CDX query changed")

    planned = release.get("planned_output", {})
    output = Path(str(planned.get("path", "")))
    raw = Path(str(planned.get("raw_response_path", "")))
    if output != EXPECTED_OUTPUT or raw != EXPECTED_OUTPUT.with_name("cdx_canary_response_v1.bin"):
        errors.append("Canary output paths changed")
    if require_output_absent and (
        output.exists()
        or output.with_suffix(output.suffix + ".partial").exists()
        or raw.exists()
    ):
        errors.append("Canary final, partial or raw output already exists")

    release_decision = release.get("decision", {})
    for field in (
        "network_execution_allowed_at_release_time",
        "candidate_live_domain_access_allowed",
        "archived_page_download_allowed",
        "artifact_capture_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "model_scoring_allowed",
        "training_allowed",
    ):
        if release_decision.get(field) is not False:
            errors.append(f"Forbidden canary decision opened: {field}")
    if release_decision.get("metadata_canary_allowed_after_not_before") is not True:
        errors.append("Post-gate metadata canary is not explicitly permitted")
    if release_decision.get("automatic_cascade_allowed") is not False:
        errors.append("Canary release permits an automatic cascade")

    return {
        "verification_id": QA_ID,
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "checks": {
            "target_rows": 1,
            "target_availability_plan_id": target.get("availability_plan_id"),
            "continuation_partial_qa_status": continuation_qa.get("status"),
            "adaptive_delay_seconds": seconds,
            "not_before": cooldown.get("not_before"),
            "maximum_network_requests": contract.get("maximum_logical_requests"),
            "metadata_only": True,
        },
        "errors": errors,
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "archived_page_downloads": 0,
            "captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.release)
    if args.output and result["status"] != "FAIL":
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite ready-channel CDX canary release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
