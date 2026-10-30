"""Crash-safe two-row PBC diagnostic runner; execution needs committed gates."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    TransportResponse,
    process_transport_response,
)
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import (
    PdfLifecycleLaunchError,
    PdfLifecycleProcessError,
    process_pdf_lifecycle_v2,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_diagnostic_release_v1 import (
    PASS_STATUS as RELEASE_PASS,
    RELEASE,
    ROOT,
    verify as verify_release,
)


RESULT = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.json"
PARTIAL = Path(str(RESULT) + ".partial")
QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_diagnostic_release_qa_v1.json"
AUTH = ROOT / "configs" / "target_text_corpus_v1_parser_bound_content_diagnostic_execution_authorization_v1.json"
USER_AGENT = "ISI-ParserBoundContent/1.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


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
    _write_exclusive(temporary, value)
    os.replace(temporary, path)


def _base_row(resource: dict) -> dict:
    return {
        "resource_id": resource["resource_id"],
        "source_endpoint_id": resource["source_endpoint_id"],
        "url": resource["url"],
        "final_url": None,
        "parser": resource["parser"],
        "outcome": None,
        "http_status": None,
        "content_type": None,
        "response_bytes": 0,
        "response_sha256": None,
        "structured_output": None,
        "raw_response_retained": False,
        "diagnostic_code": None,
        "diagnostic_details": None,
    }


def _fetch(resource: dict) -> TransportResponse:
    request = urllib.request.Request(resource["url"], headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        response = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read(int(resource["maximum_bytes"]) + 1)
        return TransportResponse(
            status_code=int(response.status),
            final_url=response.geturl(),
            headers=dict(response.headers.items()),
            body=body,
            redirect_count=0,
        )


def assemble_result(rows: list[dict], created_at: str) -> dict:
    return {
        "result_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_RESULT_V1",
        "created_at": created_at,
        "inputs": [
            {"role": "diagnostic_release", "path": RELEASE.relative_to(ROOT).as_posix(), "sha256": sha256_file(RELEASE)},
            {"role": "release_qa", "path": QA.relative_to(ROOT).as_posix(), "sha256": sha256_file(QA)},
        ],
        "resources": rows,
        "summary": {
            "resources": len(rows),
            "success": sum(row["outcome"] == "SUCCESS" for row in rows),
            "parser_rejected": sum(row["outcome"] == "PARSER_REJECTED" for row in rows),
            "http_error": sum(row["outcome"] == "HTTP_ERROR" for row in rows),
            "transport_error": sum(row["outcome"] == "TRANSPORT_ERROR" for row in rows),
            "skipped_after_failure": sum(row["outcome"] == "SKIPPED_AFTER_FAILURE" for row in rows),
            "response_bytes": sum(row["response_bytes"] for row in rows),
        },
        "safety_contract": {
            "raw_responses_retained": 0,
            "dataset_files_downloaded": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "validation_or_test_rows_opened": 0,
            "model_operations": 0,
        },
        "decision": {
            "evidence_acceptance_allowed": False,
            "dataset_acquisition_allowed": False,
            "training_allowed": False,
        },
    }


def run_with_injected_transport(
    transport: Callable[[dict], TransportResponse],
    output: Path,
    partial: Path,
    *,
    pdf_processor: Callable[[dict, bytes], dict] = process_pdf_lifecycle_v2,
    sleep_fn: Callable[[float], None] = time.sleep,
    created_at: str = "2026-10-30T00:00:00+07:00",
) -> dict:
    check = verify_release()
    if check["status"] != RELEASE_PASS:
        raise ValueError("Diagnostic release did not verify")
    if not QA.is_file():
        raise FileNotFoundError("Diagnostic release QA is absent")
    if output.exists() or partial.exists() or Path(str(partial) + ".tmp").exists():
        raise FileExistsError("Diagnostic final, partial, or temporary journal exists")
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    old = json.loads((ROOT / "registry/analyses/target_text_corpus_v1_parser_bound_content_supplemental_result_v1.json").read_text(encoding="utf-8"))
    prior_rows = {row["resource_id"]: row for row in old["resources"]}
    original = json.loads((ROOT / "configs/target_text_corpus_v1_parser_bound_content_release_v1.json").read_text(encoding="utf-8"))
    source_rows = {row["resource_id"]: row for row in original["resources"]}
    reservation = {
        "journal_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_PARTIAL_V1",
        "status": "PARTIAL_DO_NOT_AUTO_RESUME",
        "created_at": created_at,
        "release_sha256": sha256_file(RELEASE),
        "completed_resource_ids": [],
        "rows": [],
        "resume_allowed": False,
    }
    _write_exclusive(partial, reservation)
    rows: list[dict] = []
    stop = False
    try:
        for index, resource in enumerate(release["resources"]):
            if stop:
                row = _base_row(resource)
                row["outcome"] = "SKIPPED_AFTER_FAILURE"
                row["diagnostic_code"] = "EARLIER_PROVIDER_OR_TRANSPORT_FAILURE"
            else:
                if index:
                    sleep_fn(float(release["execution_contract"]["minimum_request_interval_seconds"]))
                try:
                    response = transport(resource)
                    row = process_transport_response(source_rows[resource["resource_id"]], response)
                    if row["outcome"] == "SUCCESS" and resource["resource_id"] == "PBC05":
                        try:
                            row["structured_output"] = pdf_processor(source_rows["PBC05"], response.body)
                        except PdfLifecycleProcessError as error:
                            row["outcome"] = "PARSER_REJECTED"
                            row["diagnostic_code"] = f"PDF_LIFECYCLE_{error.diagnostic_code or error.stage + '_NONZERO'}"
                            row["diagnostic_details"] = error.details
                            row["structured_output"] = None
                        except PdfLifecycleLaunchError as error:
                            row["outcome"] = "PARSER_REJECTED"
                            row["diagnostic_code"] = f"PDF_LIFECYCLE_{error.stage}_LAUNCH_ERROR"
                            row["diagnostic_details"] = error.details
                            row["structured_output"] = None
                        except Exception as error:
                            row["outcome"] = "PARSER_REJECTED"
                            row["diagnostic_code"] = "PDF_LIFECYCLE_RUNTIME_ERROR"
                            row["diagnostic_details"] = None
                            row["structured_output"] = None
                except Exception as error:
                    row = _base_row(resource)
                    row["outcome"] = "TRANSPORT_ERROR"
                    row["diagnostic_code"] = f"TRANSPORT_{type(error).__name__.upper()}"
                stop = row["outcome"] in {"HTTP_ERROR", "TRANSPORT_ERROR"}
            rows.append(row)
            _checkpoint(partial, {**reservation, "completed_resource_ids": [item["resource_id"] for item in rows], "rows": rows})
        result = assemble_result(rows, created_at)
        _checkpoint(partial, result)
        from scripts.verify_target_text_corpus_v1_parser_bound_content_diagnostic_result_v1 import verify_result

        if verify_result(partial)["status"] != "PASS_PARSER_BOUND_DIAGNOSTIC_RESULT_VERIFIED":
            raise ValueError("Independent diagnostic result verification failed")
        os.replace(partial, output)
        return {"result": result, "verification": verify_result(output)}
    except Exception:
        raise


def execution_preflight() -> dict:
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    origin = subprocess.run(["git", "rev-parse", "origin/main"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    required_paths = (
        Path(__file__), RELEASE, QA, AUTH,
        ROOT / "scripts/verify_target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.py",
    )
    tracked_paths = {
        path: subprocess.run(
            ["git", "ls-files", "--error-unmatch", path.relative_to(ROOT).as_posix()],
            cwd=ROOT, capture_output=True,
        ).returncode == 0
        for path in required_paths
    }
    auth = json.loads(AUTH.read_text(encoding="utf-8")) if AUTH.is_file() else {}
    release = verify_release()
    qa = json.loads(QA.read_text(encoding="utf-8")) if QA.is_file() else {}
    authorization = auth.get("authorization", {})
    allowed = all((
        all(tracked_paths.values()),
        not status,
        head == origin,
        release.get("status") == RELEASE_PASS,
        qa.get("status") == "PASS_EXACT_TWO_ROW_DIAGNOSTIC_RELEASE_PREPARED_EXECUTION_CLOSED",
        qa.get("release", {}).get("sha256") == sha256_file(RELEASE),
        authorization.get("received") is True,
        authorization.get("scope") == "EXECUTE_DIAGNOSTIC_RELEASE_EXACT_PBC05_PBC08",
        authorization.get("resource_ids") == ["PBC05", "PBC08"],
        authorization.get("maximum_requests") == 2,
        authorization.get("release_sha256") == sha256_file(RELEASE),
        authorization.get("repeat_prior_release_allowed") is False,
        authorization.get("retry_after_failure_allowed") is False,
        auth.get("constraints", {}).get("raw_response_retention_allowed") is False,
        auth.get("constraints", {}).get("dataset_file_download_allowed") is False,
        auth.get("constraints", {}).get("validation_or_test_open_allowed") is False,
        auth.get("constraints", {}).get("model_operations_allowed") is False,
        auth.get("constraints", {}).get("training_allowed") is False,
        not RESULT.exists() and not PARTIAL.exists() and not Path(str(PARTIAL) + ".tmp").exists(),
    ))
    return {
        "execution_allowed": allowed,
        "working_tree_clean": not status,
        "head_equals_origin_main": head == origin,
        "required_files_tracked": all(tracked_paths.values()),
        "owner_authorization_verified": authorization.get("release_sha256") == sha256_file(RELEASE),
        "network_operations": 0,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not (args.verify_only or args.execute) or args.verify_only == args.execute:
        parser.error("choose exactly one of --verify-only or --execute")
    if args.verify_only:
        print(json.dumps(execution_preflight(), ensure_ascii=False, indent=2))
        return 0
    preflight = execution_preflight()
    if preflight["execution_allowed"] is not True:
        raise PermissionError("Diagnostic execution preflight is closed")
    result = run_with_injected_transport(_fetch, RESULT, PARTIAL, created_at=datetime.now(timezone.utc).astimezone().isoformat())
    print(json.dumps(result["verification"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
