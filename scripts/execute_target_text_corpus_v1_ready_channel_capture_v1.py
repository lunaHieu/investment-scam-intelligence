"""Execute the exact-53 archive-only capture release once."""

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

from scripts.verify_target_text_corpus_v1_ready_channel_capture_release_v1 import PASS_STATUS, load, parse_time, sha256_file, verify


USER_AGENT = "ISI-Ready-Channel-Capture/1.0 (gpt-6.1; https://github.com/lunaHieu/investment-scam-intelligence)"
HEADERS = ("Retry-After", "Date", "Server", "Content-Type", "X-Archive-Wayback-Runtime-Error")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def assert_archive_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "web.archive.org" or not parsed.path.startswith("/web/") or "id_/" not in parsed.path:
        raise ValueError(f"non-archive raw replay URL: {url}")


def fetch(url: str, contract: dict[str, Any], counter: list[int]) -> tuple[bytes, str, int, str, dict[str, str]]:
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
                    raise ValueError("redirect without location") from error
                current = urllib.parse.urljoin(current, location)
                redirects += 1
                continue
            error.diagnostics = {name: str(error.headers.get(name)) for name in HEADERS if error.headers.get(name) is not None}  # type: ignore[attr-defined]
            raise
        with response:
            content_type = str(response.headers.get("Content-Type") or "")
            diagnostics = {name: str(response.headers.get(name)) for name in HEADERS if response.headers.get(name) is not None}
            if int(response.status) != 200 or not content_type.casefold().startswith("text/html"):
                raise ValueError(f"unexpected archive response: {response.status} {content_type}")
            payload = response.read(int(contract["maximum_response_bytes"]) + 1)
        if not int(contract["minimum_response_bytes"]) <= len(payload) <= int(contract["maximum_response_bytes"]):
            raise ValueError(f"archive response size outside contract: {len(payload)}")
        return payload, current, redirects, content_type, diagnostics


def validate(release_path: Path, qa_path: Path, *, require_output_absent: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    release, qa = load(release_path), load(qa_path)
    if qa.get("status") != PASS_STATUS or qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise ValueError("release QA status/hash mismatch")
    reproduced = verify(release_path, require_output_absent=require_output_absent)
    if reproduced.get("status") != PASS_STATUS:
        raise ValueError(f"release verifier failed: {reproduced.get('errors')}")
    plan_path = Path(release["inputs"]["capture_plan"]["path"])
    plan = load(plan_path)
    if sha256_file(plan_path) != release["inputs"]["capture_plan"]["sha256"]:
        raise ValueError("capture plan hash changed")
    return release, plan


def execute(release_path: Path, qa_path: Path, now: datetime | None = None, *, fetcher: Callable = fetch, output_override: Path | None = None) -> dict[str, Any]:
    release_for_gate = load(release_path)
    current = now or datetime.now(timezone.utc).astimezone()
    if current < parse_time(release_for_gate["execution_contract"]["not_before"]):
        raise PermissionError("capture not-before gate is closed")
    release, plan = validate(release_path, qa_path, require_output_absent=output_override is None)
    report_path = output_override or Path(release["planned_output"]["path"])
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    finalizing = report_path.with_suffix(report_path.suffix + ".finalizing")
    if any(path.exists() for path in (report_path, partial, finalizing)):
        raise FileExistsError("refusing to overwrite capture output state")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps({"report_id": release["planned_output"]["report_id"], "status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE", "reserved_at": current.isoformat(), "release_sha256": sha256_file(release_path), "automatic_resume_allowed": False}, indent=2) + "\n", encoding="utf-8")
    counter, results, stopped = [0], [], False
    contract = release["execution_contract"]
    for source in plan["results"]:
        base = {key: source[key] for key in ("capture_plan_id", "availability_plan_id", "candidate_id", "cohort", "channel_id", "candidate_host", "snapshot_timestamp", "snapshot_original_url", "snapshot_digest", "requested_archive_url", "capture_path")}
        target = Path(source["capture_path"]) if output_override is None else output_override.parent / "synthetic_captures" / f"{source['capture_plan_id']}.html"
        if output_override is not None:
            base["capture_path"] = str(target)
        if stopped:
            results.append({**base, "outcome": "NOT_ATTEMPTED_AFTER_ERROR_STOP", "attempt_count": 0, "http_status": None, "bytes": None, "sha256": None, "diagnostics": {}, "error": "NOT_ATTEMPTED_AFTER_ERROR_STOP"})
            continue
        try:
            payload, final_url, redirects, content_type, diagnostics = fetcher(source["requested_archive_url"], contract, counter)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            results.append({**base, "outcome": "CAPTURED", "attempt_count": 1, "final_archive_url": final_url, "redirect_count": redirects, "http_status": 200, "content_type": content_type, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "diagnostics": diagnostics, "error": None})
        except Exception as error:
            stopped = True
            status = error.code if isinstance(error, urllib.error.HTTPError) else None
            diagnostics = getattr(error, "diagnostics", {})
            results.append({**base, "outcome": "FAILED", "attempt_count": 1, "final_archive_url": None, "redirect_count": None, "http_status": status, "content_type": None, "bytes": None, "sha256": None, "diagnostics": diagnostics, "error": f"{type(error).__name__}: {error}"})
    captured = sum(row["outcome"] == "CAPTURED" for row in results)
    failed = sum(row["outcome"] == "FAILED" for row in results)
    report = {"report_id": release["planned_output"]["report_id"], "created_at": current.isoformat(), "status": "COMPLETE" if captured == 53 else "INCOMPLETE_FAILURES_PRESERVED", "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)}, "release_qa": {"path": str(qa_path.resolve()), "sha256": sha256_file(qa_path)}, "plan": release["inputs"]["capture_plan"], "planned_capture_count": 53, "network_request_count": counter[0], "captured_count": captured, "captured_by_cohort": dict(Counter(row["cohort"] for row in results if row["outcome"] == "CAPTURED")), "failed_count": failed, "not_attempted_count": sum(row["outcome"].startswith("NOT_ATTEMPTED") for row in results), "stopped_on_error": stopped, "results": results, "safety_contract": {"candidate_live_domain_access_operations": 0, "only_web_archive_host_accessed": True, "raw_replay_modifier_used": True, "labels_created": 0, "model_operations": 0, "training_allowed": False}}
    finalizing.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finalizing.replace(report_path)
    if partial.exists():
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
        remaining = max(0, (parse_time(release["execution_contract"]["not_before"]) - datetime.now(timezone.utc).astimezone()).total_seconds())
        print(json.dumps({"valid": True, "planned_capture_count": len(plan["results"]), "seconds_until_not_before": round(remaining), "user_agent": USER_AGENT}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "network_request_count", "captured_count", "captured_by_cohort", "failed_count", "not_attempted_count", "stopped_on_error")}, indent=2))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
