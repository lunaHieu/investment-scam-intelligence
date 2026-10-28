"""Execute the exact-48 capture continuation with byte-preserving row quarantine."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.execute_target_text_corpus_v1_ready_channel_capture_v1 import HEADERS, NoRedirect, assert_archive_url
from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import PASS_STATUS, load, sha, verify


USER_AGENT = "ISI-Ready-Channel-Capture-Continuation/2.0 (gpt-6.1; https://github.com/lunaHieu/investment-scam-intelligence)"


class ArchiveProviderError(RuntimeError):
    def __init__(self, message: str, *, status: int | None, payload: bytes, url: str, content_type: str, diagnostics: dict[str, str]):
        super().__init__(message)
        self.status = status
        self.payload = payload
        self.url = url
        self.content_type = content_type
        self.diagnostics = diagnostics


def fetch_response(url: str, contract: dict[str, Any], counter: list[int]) -> dict[str, Any]:
    opener = urllib.request.build_opener(NoRedirect())
    current, redirects = url, 0
    while True:
        assert_archive_url(current)
        time.sleep(float(contract["minimum_delay_seconds"]))
        counter[0] += 1
        request = urllib.request.Request(current, headers={"User-Agent": USER_AGENT}, method="GET")
        try:
            response = opener.open(request, timeout=int(contract["timeout_seconds"]))
        except urllib.error.HTTPError as error:
            if error.code in {301, 302, 303, 307, 308} and redirects < int(contract["maximum_redirects"]):
                location = error.headers.get("Location")
                if not location:
                    raise ArchiveProviderError("redirect without location", status=error.code, payload=b"", url=current, content_type="", diagnostics={}) from error
                current = urllib.parse.urljoin(current, location)
                redirects += 1
                continue
            payload = error.read(int(contract["maximum_response_bytes"]) + 1)
            diagnostics = {name: str(error.headers.get(name)) for name in HEADERS if error.headers.get(name) is not None}
            raise ArchiveProviderError(
                f"archive HTTP error: {error.code}",
                status=error.code,
                payload=payload,
                url=current,
                content_type=str(error.headers.get("Content-Type") or ""),
                diagnostics=diagnostics,
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ArchiveProviderError(
                f"archive transport error: {error}", status=None, payload=b"", url=current, content_type="", diagnostics={}
            ) from error
        with response:
            content_type = str(response.headers.get("Content-Type") or "")
            diagnostics = {name: str(response.headers.get(name)) for name in HEADERS if response.headers.get(name) is not None}
            payload = response.read(int(contract["maximum_response_bytes"]) + 1)
            status = int(response.status)
        return {
            "payload": payload,
            "url": current,
            "redirects": redirects,
            "status": status,
            "content_type": content_type,
            "diagnostics": diagnostics,
        }


def validate(release_path: Path, qa_path: Path, *, require_output_absent: bool = True) -> tuple[dict, dict]:
    release, qa = load(release_path), load(qa_path)
    reproduced = verify(release_path, require_output_absent=require_output_absent)
    if qa.get("status") != PASS_STATUS or qa.get("release", {}).get("sha256") != sha(release_path) or reproduced["status"] != PASS_STATUS:
        raise ValueError("continuation V2 release QA failed")
    return release, load(Path(release["inputs"]["continuation_plan"]["path"]))


def _write_journal(path: Path, release_hash: str, counter: int, results: list[dict]) -> None:
    temp = path.with_suffix(path.suffix + ".updating")
    value = {
        "status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE",
        "release_sha256": release_hash,
        "automatic_resume_allowed": False,
        "network_request_count": counter,
        "completed_results": results,
    }
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def execute(release_path: Path, qa_path: Path, *, fetcher: Callable = fetch_response) -> dict:
    release, plan = validate(release_path, qa_path)
    now = datetime.now(timezone.utc).astimezone()
    if now < datetime.fromisoformat(release["execution_contract"]["not_before"]):
        raise PermissionError("not-before closed")
    output = Path(release["planned_output"]["path"])
    partial = output.with_suffix(output.suffix + ".partial")
    finalizing = output.with_suffix(output.suffix + ".finalizing")
    if any(candidate.exists() for candidate in (output, partial, finalizing)):
        raise FileExistsError("output exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    release_hash = sha(release_path)
    counter, results, stopped = [0], [], False
    _write_journal(partial, release_hash, 0, results)
    contract = release["execution_contract"]
    diagnostics_root = Path(release["planned_output"]["diagnostics_root"])
    for source in plan["results"]:
        base = {key: source[key] for key in ("capture_plan_id", "availability_plan_id", "candidate_id", "cohort", "channel_id", "candidate_host", "snapshot_timestamp", "snapshot_original_url", "snapshot_digest", "requested_archive_url", "capture_path")}
        if stopped:
            results.append({**base, "outcome": "NOT_ATTEMPTED_AFTER_PROVIDER_ERROR_STOP", "attempt_count": 0, "bytes": None, "sha256": None, "error": "NOT_ATTEMPTED_AFTER_PROVIDER_ERROR_STOP"})
            continue
        diagnostic_path = diagnostics_root / source["cohort"] / f"{source['availability_plan_id']}.bin"
        try:
            response = fetcher(source["requested_archive_url"], contract, counter)
            payload = response["payload"]
            payload_hash = hashlib.sha256(payload).hexdigest()
            valid = (
                response["status"] == 200
                and response["content_type"].casefold().startswith(str(contract["required_content_type_prefix"]).casefold())
                and int(contract["minimum_response_bytes"]) <= len(payload) <= int(contract["maximum_response_bytes"])
            )
            if valid:
                target = Path(source["capture_path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as handle:
                    handle.write(payload)
                results.append({**base, "outcome": "CAPTURED", "attempt_count": 1, "final_archive_url": response["url"], "redirect_count": response["redirects"], "http_status": response["status"], "content_type": response["content_type"], "bytes": len(payload), "sha256": payload_hash, "diagnostics": response["diagnostics"], "error": None})
            else:
                diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
                with diagnostic_path.open("xb") as handle:
                    handle.write(payload)
                results.append({**base, "outcome": "QUARANTINED_ROW_LOCAL_RESPONSE", "attempt_count": 1, "final_archive_url": response["url"], "redirect_count": response["redirects"], "http_status": response["status"], "content_type": response["content_type"], "bytes": len(payload), "sha256": payload_hash, "raw_response_path": str(diagnostic_path), "diagnostics": response["diagnostics"], "error": "response outside capture content contract"})
        except ArchiveProviderError as error:
            raw_path = None
            if error.payload:
                diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
                with diagnostic_path.open("xb") as handle:
                    handle.write(error.payload)
                raw_path = str(diagnostic_path)
            stopped = True
            results.append({**base, "outcome": "FAILED_PROVIDER_OR_TRANSPORT", "attempt_count": 1, "final_archive_url": error.url, "http_status": error.status, "content_type": error.content_type, "bytes": len(error.payload) if error.payload else None, "sha256": hashlib.sha256(error.payload).hexdigest() if error.payload else None, "raw_response_path": raw_path, "diagnostics": error.diagnostics, "error": str(error)})
        _write_journal(partial, release_hash, counter[0], results)
    captured = sum(row["outcome"] == "CAPTURED" for row in results)
    quarantined = sum(row["outcome"] == "QUARANTINED_ROW_LOCAL_RESPONSE" for row in results)
    failed = sum(row["outcome"] == "FAILED_PROVIDER_OR_TRANSPORT" for row in results)
    not_attempted = sum(row["outcome"].startswith("NOT_ATTEMPTED") for row in results)
    status = "COMPLETE" if captured == 48 else "COMPLETE_WITH_ROW_QUARANTINES" if captured + quarantined == 48 and failed == 0 else "INCOMPLETE_PROVIDER_FAILURE_PRESERVED"
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": now.isoformat(),
        "status": status,
        "release": {"sha256": release_hash},
        "release_qa": {"sha256": sha(qa_path)},
        "plan": release["inputs"]["continuation_plan"],
        "planned_capture_count": 48,
        "network_request_count": counter[0],
        "captured_count": captured,
        "captured_by_cohort": dict(Counter(row["cohort"] for row in results if row["outcome"] == "CAPTURED")),
        "quarantined_row_local_count": quarantined,
        "failed_provider_or_transport_count": failed,
        "not_attempted_count": not_attempted,
        "stopped_on_provider_or_transport_error": stopped,
        "results": results,
        "safety_contract": {"candidate_live_domain_access_operations": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }
    finalizing.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finalizing.replace(output)
    partial.unlink()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release, plan = validate(args.release, args.release_qa)
        remaining = max(0, round((datetime.fromisoformat(release["execution_contract"]["not_before"]) - datetime.now(timezone.utc).astimezone()).total_seconds()))
        print(json.dumps({"valid": True, "planned_capture_count": len(plan["results"]), "seconds_until_not_before": remaining, "user_agent": USER_AGENT}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("status", "network_request_count", "captured_count", "quarantined_row_local_count", "failed_provider_or_transport_count", "not_attempted_count")}, indent=2))
    return 0 if report["status"] in {"COMPLETE", "COMPLETE_WITH_ROW_QUARANTINES"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
