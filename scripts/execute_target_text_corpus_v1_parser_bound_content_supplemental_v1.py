"""Crash-safe supplemental state machine; live network capability is absent."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Callable

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    TransportResponse,
    process_transport_response,
)
from scripts.orchestrate_target_text_corpus_v1_parser_bound_content_v1 import _base_row
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import (
    PdfLifecycleLaunchError,
    PdfLifecycleProcessError,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE as V1_RELEASE, ROOT
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_release_v1 import RELEASE, verify as verify_release
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_result_v1 import verify_result


QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_supplemental_release_qa_v1.json"
V1_RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_result_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_exclusive(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _checkpoint(path: Path, value: dict) -> None:
    temporary = Path(str(path) + ".tmp")
    if temporary.exists():
        raise FileExistsError("Stale supplemental checkpoint temp exists")
    _write_exclusive(temporary, value)
    os.replace(temporary, path)


def _transport_error_row(resource: dict, error: Exception) -> dict:
    row = _base_row(resource)
    row["outcome"] = "TRANSPORT_ERROR"
    row["diagnostic_code"] = f"TRANSPORT_{type(error).__name__.upper()}"
    row["diagnostic_details"] = None
    return row


def _skipped_row(resource: dict) -> dict:
    row = _base_row(resource)
    row["diagnostic_code"] = "EARLIER_PROVIDER_OR_TRANSPORT_FAILURE"
    row["diagnostic_details"] = None
    return row


def _apply_pdf_processor(row: dict, resource: dict, body: bytes, pdf_processor: Callable[[dict, bytes], dict]) -> dict:
    try:
        row["structured_output"] = pdf_processor(resource, body)
        row["diagnostic_details"] = None
    except PdfLifecycleProcessError as error:
        row["outcome"] = "PARSER_REJECTED"
        row["structured_output"] = None
        row["diagnostic_code"] = f"PDF_LIFECYCLE_{error.diagnostic_code or error.stage + '_NONZERO'}"
        row["diagnostic_details"] = error.details
    except PdfLifecycleLaunchError as error:
        row["outcome"] = "PARSER_REJECTED"
        row["structured_output"] = None
        row["diagnostic_code"] = f"PDF_LIFECYCLE_{error.stage}_LAUNCH_ERROR"
        row["diagnostic_details"] = None
    except Exception as error:
        row["outcome"] = "PARSER_REJECTED"
        row["structured_output"] = None
        row["diagnostic_code"] = f"PDF_LIFECYCLE_{type(error).__name__.upper()}"
        row["diagnostic_details"] = None
    return row


def assemble_result(rows: list[dict], created_at: str) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    return {
        "result_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_SUPPLEMENTAL_RESULT_V1",
        "created_at": created_at,
        "inputs": [
            {"role": "supplemental_release", "path": str(RELEASE.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(RELEASE)},
            {"role": "supplemental_release_qa", "path": str(QA.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(QA)},
            {"role": "immutable_v1_result", "path": str(V1_RESULT.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(V1_RESULT)},
        ],
        "resources": rows,
        "summary": {
            "resources": len(rows),
            "success": counts["SUCCESS"],
            "parser_rejected": counts["PARSER_REJECTED"],
            "http_error": counts["HTTP_ERROR"],
            "transport_error": counts["TRANSPORT_ERROR"],
            "skipped_after_failure": counts["SKIPPED_AFTER_FAILURE"],
            "response_bytes": sum(row["response_bytes"] for row in rows),
        },
        "safety_contract": {
            "raw_responses_retained": 0,
            "dataset_files_downloaded": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "validation_or_test_rows_opened": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
        "decision": {"evidence_acceptance_allowed": False, "dataset_acquisition_allowed": False, "training_allowed": False},
    }


def execute_with_injected_transport_for_test(
    transport: Callable[[dict], TransportResponse],
    pdf_processor: Callable[[dict, bytes], dict],
    output: Path,
    partial: Path,
    *,
    created_at: str = "2026-10-30T00:00:00+07:00",
) -> dict:
    release_check = verify_release()
    if release_check["status"] != "PASS_EXACT_PBC05_PBC08_SUPPLEMENTAL_RELEASE_EXECUTION_CLOSED":
        raise ValueError("Supplemental release no longer verifies")
    if not QA.is_file():
        raise FileNotFoundError("Supplemental release QA is absent")
    checkpoint_temp = Path(str(partial) + ".tmp")
    if output.exists() or partial.exists() or checkpoint_temp.exists():
        raise FileExistsError("Supplemental final, partial, or checkpoint temp exists")
    v1 = json.loads(V1_RELEASE.read_text(encoding="utf-8"))
    resources_by_id = {item["resource_id"]: item for item in v1["resources"]}
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    resources = [resources_by_id[item] for item in release["resource_ids"]]
    reservation = {
        "journal_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_SUPPLEMENTAL_PARTIAL_V1",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "created_at": created_at,
        "release_sha256": sha256_file(RELEASE),
        "release_qa_sha256": sha256_file(QA),
        "completed_resource_ids": [],
        "rows": [],
        "resume_allowed": False,
    }
    _write_exclusive(partial, reservation)
    rows: list[dict] = []
    provider_failure_seen = False
    for resource in resources:
        if provider_failure_seen:
            row = _skipped_row(resource)
        else:
            try:
                response = transport(resource)
                row = process_transport_response(resource, response)
                row["diagnostic_details"] = None
                if row["outcome"] == "SUCCESS" and resource["resource_id"] == "PBC05":
                    row = _apply_pdf_processor(row, resource, response.body, pdf_processor)
            except Exception as error:
                row = _transport_error_row(resource, error)
            provider_failure_seen = row["outcome"] in {"HTTP_ERROR", "TRANSPORT_ERROR"}
        rows.append(row)
        _checkpoint(partial, {**reservation, "completed_resource_ids": [item["resource_id"] for item in rows], "rows": rows})
    result = assemble_result(rows, created_at)
    _checkpoint(partial, result)
    verification = verify_result(partial)
    if verification["status"] != "PASS_PARSER_BOUND_SUPPLEMENTAL_RESULT_VERIFIED":
        raise ValueError("Supplemental independent verification failed")
    os.replace(partial, output)
    return {"result": result, "verification": verification}


if __name__ == "__main__":
    print(json.dumps({"status": "PASS_SUPPLEMENTAL_STATE_MACHINE_IMPLEMENTED_LIVE_CAPABILITY_ABSENT"}, ensure_ascii=False))
