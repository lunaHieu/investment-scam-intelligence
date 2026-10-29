"""Crash-safe parser-bound orchestrator; live execution remains hard-disabled."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    LOCAL_QA,
    TransportResponse,
    process_transport_response,
)
from scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1 import (
    authorize_live_transport,
    live_transport,
)
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v1 import (
    process_pdf_lifecycle,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
    ROOT,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_result_v1 import (
    verify_result,
)


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
        raise FileExistsError(f"Stale checkpoint temp exists: {temporary}")
    _write_exclusive(temporary, value)
    os.replace(temporary, path)


def _base_row(resource: dict) -> dict:
    return {
        "resource_id":resource["resource_id"],
        "source_endpoint_id":resource["source_endpoint_id"],
        "url":resource["url"],
        "final_url":None,
        "parser":resource["parser"],
        "outcome":"SKIPPED_AFTER_FAILURE",
        "http_status":None,
        "content_type":None,
        "response_bytes":0,
        "response_sha256":None,
        "structured_output":None,
        "raw_response_retained":False,
        "diagnostic_code":"EARLIER_RESOURCE_FAILED",
    }


def _transport_error_row(resource: dict, error: Exception) -> dict:
    row = _base_row(resource)
    row["outcome"] = "TRANSPORT_ERROR"
    row["diagnostic_code"] = f"TRANSPORT_{type(error).__name__.upper()}"
    return row


def assemble_result(rows: list[dict], created_at: str) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    return {
        "result_id":"ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_RESULT_V1",
        "created_at":created_at,
        "inputs":[
            {"role":"release", "path":str(RELEASE.relative_to(ROOT)).replace("\\", "/"), "sha256":sha256_file(RELEASE)},
            {"role":"release_qa", "path":str(LOCAL_QA.relative_to(ROOT)).replace("\\", "/"), "sha256":sha256_file(LOCAL_QA)},
        ],
        "resources":rows,
        "summary":{
            "resources":len(rows),
            "success":counts["SUCCESS"],
            "parser_rejected":counts["PARSER_REJECTED"],
            "http_error":counts["HTTP_ERROR"],
            "transport_error":counts["TRANSPORT_ERROR"],
            "skipped_after_failure":counts["SKIPPED_AFTER_FAILURE"],
            "response_bytes":sum(row["response_bytes"] for row in rows),
        },
        "safety_contract":{
            "raw_responses_retained":0,
            "dataset_files_downloaded":0,
            "candidate_domain_access_operations":0,
            "labels_created":0,
            "validation_or_test_rows_opened":0,
            "model_operations":0,
            "training_allowed":False,
        },
        "decision":{
            "evidence_acceptance_allowed":False,
            "dataset_acquisition_allowed":False,
            "training_allowed":False,
        },
    }


def execute_with_injected_transport_for_test(
    transport: Callable[[dict], TransportResponse],
    output: Path,
    partial: Path,
    *,
    verifier: Callable[[Path], dict] = verify_result,
    pdf_processor: Callable[[dict, bytes], dict] | None = None,
    created_at: str = "2026-10-29T00:00:00+00:00",
) -> dict:
    """Exercise the production state machine with a caller-provided transport."""

    release_check = verify_release(require_absent=False)
    if release_check["status"] != "PASS_LOCAL_PARSER_BOUND_RELEASE_VERIFIED_EXECUTION_CLOSED":
        raise ValueError("Release verification failed")
    checkpoint_temp = Path(str(partial) + ".tmp")
    if output.exists() or partial.exists() or checkpoint_temp.exists():
        raise FileExistsError("Final, partial, or checkpoint temp already exists")
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    reservation = {
        "journal_id":"ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_PARTIAL_V1",
        "status":"PARTIAL_DO_NOT_AUTO_RESUME",
        "created_at":created_at,
        "release_sha256":sha256_file(RELEASE),
        "release_qa_sha256":sha256_file(LOCAL_QA),
        "completed_resource_ids":[],
        "rows":[],
        "resume_allowed":False,
    }
    _write_exclusive(partial, reservation)

    rows: list[dict] = []
    stopped = False
    for resource in release["resources"]:
        if stopped:
            row = _base_row(resource)
        else:
            try:
                response = transport(resource)
                row = process_transport_response(resource, response)
                if (
                    row["outcome"] == "SUCCESS"
                    and resource["resource_id"] == "PBC05"
                    and pdf_processor is not None
                ):
                    try:
                        row["structured_output"] = pdf_processor(resource, response.body)
                    except Exception as error:
                        row["outcome"] = "PARSER_REJECTED"
                        row["structured_output"] = None
                        row["diagnostic_code"] = f"PDF_LIFECYCLE_{type(error).__name__.upper()}"
            except Exception as error:
                row = _transport_error_row(resource, error)
            stopped = row["outcome"] != "SUCCESS"
        rows.append(row)
        checkpoint = {
            **reservation,
            "completed_resource_ids":[item["resource_id"] for item in rows],
            "rows":rows,
        }
        _checkpoint(partial, checkpoint)

    result = assemble_result(rows, created_at)
    _checkpoint(partial, result)
    verification = verifier(partial)
    if verification["status"] != "PASS_PARSER_BOUND_CONTENT_RESULT_VERIFIED":
        raise ValueError("Independent result verification did not pass")
    os.replace(partial, output)
    return {"result":result, "verification":verification}


def execute_live() -> dict:
    """Production entry point; currently stops before any opener can be built."""

    capability = authorize_live_transport()
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    output = ROOT / release["planned_output"]
    partial = ROOT / release["planned_partial"]
    created_at = datetime.now(timezone.utc).astimezone().isoformat()
    return execute_with_injected_transport_for_test(
        lambda resource:live_transport(resource, capability),
        output,
        partial,
        pdf_processor=lambda resource, data:process_pdf_lifecycle(resource, data),
        created_at=created_at,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if not args.verify_only:
        raise PermissionError("Live orchestration has no CLI while the release is local")
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    print(json.dumps({
        "status":"PASS_PRODUCTION_ORCHESTRATOR_IMPLEMENTED_LIVE_EXECUTION_CLOSED",
        "partial_format":release["orchestrator_contract"]["partial_format"],
        "planned_output_exists":(ROOT / release["planned_output"]).exists(),
        "planned_partial_exists":(ROOT / release["planned_partial"]).exists(),
        "execution_allowed":release["decision"]["execution_allowed_now"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
