"""Execute the frozen V11 two-row supplemental archive-only capture release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_release import parse_time
from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url
from scripts.verify_sec_edgar_iapd_v11_supplemental_capture_release import (
    RELEASE_QA_STATUS,
    verify as verify_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


MAX_CAPTURE_BYTES = 25 * 1024 * 1024
USER_AGENT = "ISI-V11-Supplemental-Capture/1.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"
ALLOWED_DIAGNOSTIC_HEADERS = ("Retry-After", "Date", "Server", "Content-Type", "X-Archive-Wayback-Runtime-Error")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _headers(headers: Any) -> dict[str, str]:
    return {name: str(headers.get(name) or "") for name in ALLOWED_DIAGNOSTIC_HEADERS if headers.get(name) is not None}


def fetch_archive(url: str, *, timeout_seconds: int, delay_seconds: float, request_counter: list[int], max_redirects: int) -> tuple[bytes, str, int, str, dict[str, str]]:
    opener = urllib.request.build_opener(NoRedirect())
    current = url
    redirects = 0
    while True:
        assert_archive_url(current)
        time.sleep(delay_seconds)
        request = urllib.request.Request(current, headers={"User-Agent": USER_AGENT}, method="GET")
        request_counter[0] += 1
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except urllib.error.HTTPError as error:
            if error.code in {301, 302, 303, 307, 308}:
                if redirects >= max_redirects:
                    raise ValueError("Maximum archive redirect count exceeded") from error
                location = error.headers.get("Location")
                if not location:
                    raise ValueError(f"HTTP {error.code} without a redirect location") from error
                current = urllib.parse.urljoin(current, location)
                assert_archive_url(current)
                redirects += 1
                continue
            error.diagnostics = _headers(error.headers)  # type: ignore[attr-defined]
            raise
        with response:
            status = int(response.status)
            diagnostics = _headers(response.headers)
            if status != 200:
                raise ValueError(f"Unexpected HTTP status: {status}")
            content_type = str(response.headers.get("Content-Type") or "")
            if not content_type.casefold().startswith("text/html"):
                raise ValueError(f"Unexpected content type: {content_type}")
            payload = response.read(MAX_CAPTURE_BYTES + 1)
        if len(payload) > MAX_CAPTURE_BYTES:
            raise ValueError("Archived HTML capture exceeds the size limit")
        if len(payload) < 1024:
            raise ValueError(f"Archived HTML capture is unexpectedly small: {len(payload)} bytes")
        return payload, current, redirects, content_type, diagnostics


def validate_release(release_path: Path, qa_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    release = load_object(release_path)
    qa = load_object(qa_path)
    errors: list[str] = []
    if qa.get("status") != RELEASE_QA_STATUS or qa.get("release", {}).get("sha256") != sha256_file(release_path):
        errors.append("Supplemental release QA status or hash binding mismatch")
    reproduced = verify_release(release_path)
    if reproduced.get("status") != RELEASE_QA_STATUS or reproduced.get("errors"):
        errors.append("Supplemental release no longer passes its frozen verifier")
    plan_path = Path(str(release["inputs"]["capture_plan"]["path"]))
    if sha256_file(plan_path) != release["inputs"]["capture_plan"]["sha256"]:
        errors.append("Supplemental capture plan hash changed")
    plan = load_object(plan_path)
    report_path = Path(str(release["planned_output"]["path"]))
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    if report_path.exists() or partial.exists():
        errors.append("Supplemental capture report or partial journal already exists")
    existing = [row["capture_path"] for row in plan["results"] if Path(row["capture_path"]).exists()]
    if existing:
        errors.append("One or more supplemental raw capture targets already exist")
    if errors:
        raise ValueError(f"Supplemental capture execution validation failed: {errors}")
    return release, plan


def _base_row(source: dict[str, Any]) -> dict[str, Any]:
    return {key: source[key] for key in (
        "availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url",
        "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path",
    )}


def execute(release_path: Path, qa_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release, plan = validate_release(release_path, qa_path)
    current = now or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    not_before = parse_time(str(release["execution_contract"]["not_before"]))
    if current < not_before:
        raise PermissionError(f"Supplemental capture not-before gate is closed for {(not_before - current).total_seconds():.0f} seconds")
    report_path = Path(str(release["planned_output"]["path"]))
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    reservation = {
        "report_id": release["planned_output"]["report_id"],
        "status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE",
        "reserved_at": current.isoformat(),
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(qa_path),
        "planned_capture_count": len(plan["results"]),
        "network_operations_started": False,
        "automatic_resume_allowed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if partial.exists() or report_path.exists():
        raise FileExistsError("Refusing to overwrite supplemental capture reservation or report")
    partial.write_text(json.dumps(reservation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    request_counter = [0]
    results: list[dict[str, Any]] = []
    stopped = False
    contract = release["execution_contract"]
    for source in plan["results"]:
        base = _base_row(source)
        if stopped:
            results.append({**base, "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP", "final_archive_url": None, "redirect_count": None, "http_status": None, "content_type": None, "bytes": None, "sha256": None, "attempt_count": 0, "diagnostics": {}, "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP"})
            continue
        try:
            payload, final_url, redirects, content_type, diagnostics = fetch_archive(
                source["requested_archive_url"],
                timeout_seconds=int(contract["timeout_seconds"]),
                delay_seconds=float(contract["minimum_delay_seconds"]),
                request_counter=request_counter,
                max_redirects=int(contract["maximum_redirects"]),
            )
            target = Path(source["capture_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            results.append({**base, "outcome": "CAPTURED", "final_archive_url": final_url, "redirect_count": redirects, "http_status": 200, "content_type": content_type, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "attempt_count": 1, "diagnostics": diagnostics, "error": None})
        except urllib.error.HTTPError as error:
            if error.code == 429:
                stopped = True
            results.append({**base, "outcome": "FAILED", "final_archive_url": None, "redirect_count": None, "http_status": error.code, "content_type": None, "bytes": None, "sha256": None, "attempt_count": 1, "diagnostics": getattr(error, "diagnostics", _headers(error.headers)), "error": f"HTTPError: {error}"})
        except Exception as error:
            results.append({**base, "outcome": "FAILED", "final_archive_url": None, "redirect_count": None, "http_status": None, "content_type": None, "bytes": None, "sha256": None, "attempt_count": 1, "diagnostics": {}, "error": f"{type(error).__name__}: {error}"})

    captured = sum(row["outcome"] == "CAPTURED" for row in results)
    failed = sum(row["outcome"] == "FAILED" for row in results)
    not_attempted = sum(row["outcome"] == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP" for row in results)
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": current.isoformat(),
        "status": "COMPLETE" if captured == len(results) else "INCOMPLETE_FAILURES_PRESERVED",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "release_qa": {"path": str(qa_path.resolve()), "sha256": sha256_file(qa_path)},
        "plan": release["inputs"]["capture_plan"],
        "planned_capture_count": len(results),
        "network_request_count": request_counter[0],
        "captured_count": captured,
        "captured_by_cohort": dict(Counter(row["cohort"] for row in results if row["outcome"] == "CAPTURED")),
        "failed_count": failed,
        "not_attempted_count": not_attempted,
        "stopped_on_http_429": stopped,
        "results": results,
        "safety_contract": {"candidate_live_domain_access_operations": 0, "only_web_archive_host_accessed": True, "raw_replay_modifier_used": True, "automatic_external_redirect_following": False, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }
    partial.replace(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release, plan = validate_release(args.release, args.release_qa)
        remaining = max(0.0, (parse_time(str(release["execution_contract"]["not_before"])) - datetime.now(timezone.utc).astimezone()).total_seconds())
        print(json.dumps({"valid": True, "planned_capture_count": len(plan["results"]), "seconds_until_not_before": round(remaining), "user_agent": USER_AGENT}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "planned_capture_count", "network_request_count", "captured_count", "captured_by_cohort", "failed_count", "not_attempted_count", "stopped_on_http_429")}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
