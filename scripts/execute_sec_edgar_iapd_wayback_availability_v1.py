"""Execute the frozen SEC/IAPD Wayback availability plan with fail-closed guards."""

from __future__ import annotations

import argparse
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

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class RateLimitStop(RuntimeError):
    """Stop all remaining availability requests after HTTP 429."""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def assert_archive_url(value: str, allowed_hosts: set[str]) -> None:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or host not in allowed_hosts:
        raise ValueError(f"Archive-only network guard rejected URL: {value}")


def normalize_snapshot_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme not in {"http", "https"} or host != "web.archive.org":
        raise ValueError("Wayback response contains non-archive snapshot URL")
    if not re.match(r"^/web/\d{14}/https?://", parsed.path):
        raise ValueError("Wayback response contains malformed snapshot URL")
    return parsed._replace(scheme="https").geturl()


def parse_response(payload: dict[str, Any]) -> dict[str, Any]:
    snapshots = payload.get("archived_snapshots")
    if not isinstance(snapshots, dict):
        raise ValueError("Wayback response lacks archived_snapshots")
    closest = snapshots.get("closest")
    if closest is None:
        return {"available": False, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None}
    if not isinstance(closest, dict):
        raise ValueError("Wayback closest snapshot is malformed")
    if closest.get("available") is not True:
        return {"available": False, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None}
    timestamp = str(closest.get("timestamp") or "")
    status = str(closest.get("status") or "")
    if not re.fullmatch(r"\d{14}", timestamp) or status != "200":
        raise ValueError("Available Wayback snapshot lacks valid timestamp/status")
    return {"available": True, "snapshot_timestamp": timestamp, "snapshot_url": normalize_snapshot_url(str(closest.get("url") or "")), "snapshot_http_status": status}


def fetch_json(url: str, contract: dict[str, Any], request_counter: list[int]) -> dict[str, Any]:
    allowed = {str(host).casefold() for host in contract["allowed_network_hosts"]}
    opener = urllib.request.build_opener(NoRedirect())
    current = url
    redirects = 0
    while True:
        assert_archive_url(current, allowed)
        time.sleep(float(contract["minimum_delay_seconds"]))
        request = urllib.request.Request(current, headers={"User-Agent": "ISI-Research/1.0 (academic archive availability)"}, method="GET")
        request_counter[0] += 1
        try:
            response = opener.open(request, timeout=int(contract["timeout_seconds"]))
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise RateLimitStop("Wayback availability endpoint returned HTTP 429") from error
            if error.code in {301, 302, 303, 307, 308}:
                if redirects >= int(contract["maximum_redirects"]):
                    raise ValueError("Maximum archive redirect count exceeded") from error
                location = error.headers.get("Location")
                if not location:
                    raise ValueError("Archive redirect omitted Location") from error
                current = urllib.parse.urljoin(current, location)
                assert_archive_url(current, allowed)
                redirects += 1
                continue
            raise
        with response:
            if int(response.status) != 200:
                raise ValueError(f"Unexpected HTTP status: {response.status}")
            limit = int(contract["maximum_response_bytes"])
            payload = response.read(limit + 1)
        if len(payload) > limit:
            raise ValueError("Wayback availability response exceeds size limit")
        value = json.loads(payload.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Wayback availability response is not a JSON object")
        return value


def validate_release(release_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    release = load_object(release_path)
    if release.get("release_id") != "ISI_SEC_EDGAR_IAPD_WAYBACK_AVAILABILITY_EXECUTION_RELEASE_V1":
        raise ValueError("Unexpected availability execution release")
    if release.get("status") != "FROZEN_RATE_LIMITED_ARCHIVE_ONLY_AVAILABILITY_EXECUTION_AUTHORIZED_CAPTURE_BLOCKED":
        raise PermissionError("Availability execution release status is not authorized")
    root = release_path.resolve().parents[1]
    for item in release["basis"]:
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Availability execution basis mismatch: {item['role']}")
    for item in release["inputs"].values():
        path = Path(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError("Availability execution input hash mismatch")
    verification = load_object(Path(release["inputs"]["plan_independent_verification"]["path"]))
    if verification.get("status") != release["inputs"]["plan_independent_verification"]["required_status"]:
        raise ValueError("Availability plan independent verification is not PASS")
    decision = release["decision"]
    if decision.get("wayback_availability_query_execution_allowed") is not True:
        raise PermissionError("Wayback availability execution is closed")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            raise PermissionError(f"Availability execution opened forbidden gate: {gate}")
    contract = release["execution_contract"]
    if contract["endpoint"] != "https://archive.org/wayback/available" or set(contract["allowed_network_hosts"]) != {"archive.org", "web.archive.org"}:
        raise ValueError("Availability execution endpoint/host allowlist changed")
    if float(contract["minimum_delay_seconds"]) < 6.0 or int(contract["maximum_attempts_per_candidate"]) != 1 or contract["stop_on_http_429"] is not True:
        raise ValueError("Availability execution rate/attempt guards changed")
    plan = read_jsonl(Path(release["inputs"]["availability_plan"]["path"]))
    if len(plan) != int(contract["expected_candidate_count"]):
        raise ValueError("Availability execution plan count mismatch")
    counts = Counter(row["cohort"] for row in plan)
    if counts != Counter({"DEVELOPMENT": int(contract["expected_development_count"]), "EXTERNAL_HOLDOUT": int(contract["expected_external_holdout_count"])}):
        raise ValueError("Availability execution cohort counts changed")
    allowed = set(contract["allowed_network_hosts"])
    for row in plan:
        assert_archive_url(row["planned_request_url"], allowed)
        if row["plan_status"] != "PLANNED_NOT_EXECUTED" or row["wayback_queried"] is not False:
            raise ValueError("Availability plan state changed before execution")
    return release, plan


def execute(release_path: Path) -> dict[str, Any]:
    release, plan = validate_release(release_path)
    output_path = Path(release["planned_output"]["path"])
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    if output_path.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite availability result")
    contract = release["execution_contract"]
    request_counter = [0]
    results: list[dict[str, Any]] = []
    stopped_on_429 = False
    for index, row in enumerate(plan, start=1):
        base = {
            "availability_plan_id": row["availability_plan_id"], "shortlist_id": row["shortlist_id"],
            "cohort": row["cohort"], "candidate_host": row["candidate_host"], "candidate_url": row["candidate_url"],
            "query_timestamp": row["target_timestamp"],
        }
        if stopped_on_429:
            results.append({**base, "queried": False, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None, "error": "NOT_QUERIED_AFTER_HTTP_429_STOP"})
            continue
        try:
            payload = fetch_json(row["planned_request_url"], contract, request_counter)
            parsed = parse_response(payload)
            results.append({**base, "queried": True, **parsed, "error": None})
        except RateLimitStop as error:
            stopped_on_429 = True
            results.append({**base, "queried": True, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": "429", "error": f"{type(error).__name__}: {error}"})
        except Exception as error:
            results.append({**base, "queried": True, "available": None, "snapshot_timestamp": None, "snapshot_url": None, "snapshot_http_status": None, "error": f"{type(error).__name__}: {error}"})
        if index % 10 == 0 or index == len(plan):
            print(json.dumps({"progress": index, "total": len(plan), "network_requests": request_counter[0], "stopped_on_429": stopped_on_429}), flush=True)
    unresolved = sum(row["error"] is not None for row in results)
    available = sum(row["available"] is True for row in results)
    unavailable = sum(row["available"] is False for row in results)
    by_cohort = {
        cohort: {
            "total": sum(row["cohort"] == cohort for row in results),
            "available": sum(row["cohort"] == cohort and row["available"] is True for row in results),
            "unavailable": sum(row["cohort"] == cohort and row["available"] is False for row in results),
            "unresolved": sum(row["cohort"] == cohort and row["error"] is not None for row in results),
        }
        for cohort in ("DEVELOPMENT", "EXTERNAL_HOLDOUT")
    }
    report = {
        "report_id": release["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED",
        "release_path": str(release_path.resolve()), "release_sha256": sha256_file(release_path),
        "plan_path": release["inputs"]["availability_plan"]["path"], "plan_sha256": release["inputs"]["availability_plan"]["sha256"],
        "requested_candidate_count": len(plan), "network_request_count": request_counter[0],
        "available_snapshot_count": available, "unavailable_snapshot_count": unavailable,
        "unresolved_error_count": unresolved, "stopped_on_http_429": stopped_on_429,
        "capture_plan_construction_ready": unresolved == 0,
        "counts_by_cohort": by_cohort,
        "results": results,
        "safety_contract": {"candidate_live_domain_access_operations": 0, "only_archive_availability_hosts_accessed": True, "archived_page_download_operations": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(output_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release, plan = validate_release(args.release)
        print(json.dumps({"valid": True, "release_id": release["release_id"], "plan_rows": len(plan), "network_execution_allowed": True}, indent=2))
        return 0
    report = execute(args.release)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "requested_candidate_count", "network_request_count", "available_snapshot_count", "unavailable_snapshot_count", "unresolved_error_count", "stopped_on_http_429", "capture_plan_construction_ready")}, ensure_ascii=False, indent=2))
    return 0 if report["capture_plan_construction_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
