"""Safely query Wayback availability for the frozen Target Text Corpus V1 queue."""

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


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_AVAILABILITY_V1"
EXPECTED_STATUS = "FROZEN_WAYBACK_AVAILABILITY_QUERY_AUTHORIZED_CAPTURE_BLOCKED"
EXPECTED_CHANNEL_COUNTS = {
    "CONFIRMED_REGULATOR_LINKED_WEBSITE": 10,
    "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": 10,
    "LEGITIMATE_REGISTER_LINKED_WEBSITE": 10,
    "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": 10,
}
ALLOWED_ARCHIVE_HOSTS = {"archive.org", "web.archive.org"}
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class RateLimitStop(RuntimeError):
    """Signal a fail-closed stop after HTTP 429."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def assert_archive_url(value: str) -> None:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or host not in ALLOWED_ARCHIVE_HOSTS:
        raise ValueError(f"Archive-only network guard rejected URL: {value}")


def availability_url(endpoint: str, candidate_url: str, timestamp: str) -> str:
    assert_archive_url(endpoint)
    if not re.fullmatch(r"\d{8}", timestamp):
        raise ValueError("Wayback target timestamp must be YYYYMMDD")
    parsed_candidate = urllib.parse.urlparse(candidate_url)
    if parsed_candidate.scheme not in {"http", "https"} or not parsed_candidate.hostname:
        raise ValueError(f"Invalid candidate URL: {candidate_url}")
    query = urllib.parse.urlencode({"url": candidate_url, "timestamp": timestamp})
    return f"{endpoint}?{query}"


def normalize_snapshot_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme not in {"http", "https"} or host != "web.archive.org":
        raise ValueError(f"Unexpected Wayback snapshot URL: {value}")
    if not re.match(r"^/web/\d{14}/https?://", parsed.path):
        raise ValueError(f"Malformed Wayback snapshot URL: {value}")
    return parsed._replace(scheme="https").geturl()


def parse_availability_response(payload: dict[str, Any]) -> dict[str, Any]:
    snapshots = payload.get("archived_snapshots")
    if not isinstance(snapshots, dict):
        raise ValueError("Wayback response lacks archived_snapshots")
    closest = snapshots.get("closest")
    if closest is None:
        return {
            "available": False,
            "snapshot_timestamp": None,
            "snapshot_url": None,
            "snapshot_http_status": None,
        }
    if not isinstance(closest, dict):
        raise ValueError("Wayback closest snapshot is malformed")
    if closest.get("available") is not True:
        return {
            "available": False,
            "snapshot_timestamp": None,
            "snapshot_url": None,
            "snapshot_http_status": str(closest.get("status") or "") or None,
        }
    timestamp = str(closest.get("timestamp") or "")
    status = str(closest.get("status") or "")
    if not re.fullmatch(r"\d{14}", timestamp) or status != "200":
        raise ValueError("Wayback available snapshot lacks a valid timestamp/status")
    return {
        "available": True,
        "snapshot_timestamp": timestamp,
        "snapshot_url": normalize_snapshot_url(str(closest.get("url") or "")),
        "snapshot_http_status": status,
    }


def fetch_json(
    url: str, *, timeout_seconds: int, delay_seconds: float, request_counter: list[int]
) -> dict[str, Any]:
    opener = urllib.request.build_opener(NoRedirect())
    current = url
    redirects = 0
    while True:
        assert_archive_url(current)
        time.sleep(delay_seconds)
        request = urllib.request.Request(
            current,
            headers={"User-Agent": "ISI-Research/1.0 (academic archive availability)"},
            method="GET",
        )
        request_counter[0] += 1
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise RateLimitStop("Wayback availability endpoint returned HTTP 429") from error
            if error.code in {301, 302, 303, 307, 308}:
                if redirects >= 3:
                    raise ValueError("Maximum archive redirect count exceeded") from error
                location = error.headers.get("Location")
                if not location:
                    raise ValueError(f"HTTP {error.code} without redirect location") from error
                current = urllib.parse.urljoin(current, location)
                assert_archive_url(current)
                redirects += 1
                continue
            raise
        with response:
            if int(response.status) != 200:
                raise ValueError(f"Unexpected HTTP status: {response.status}")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("Wayback availability response exceeds size limit")
        value = json.loads(payload.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Wayback availability response is not a JSON object")
        return value


def validate_protocol(protocol_path: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    root = protocol_path.resolve().parents[1]
    errors: list[str] = []
    role_paths: dict[str, Path] = {}
    if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        errors.append("Unexpected protocol ID")
    if protocol.get("status") != EXPECTED_STATUS:
        errors.append("Unexpected protocol status")
    for item in protocol.get("basis", []):
        role = str(item.get("role"))
        path = resolve(root, item.get("path", ""))
        role_paths[role] = path
        actual = sha256_file(path) if path.is_file() else None
        if actual != item.get("sha256"):
            errors.append(f"Basis artifact missing or changed: {role}")
    queue_path = role_paths.get("frozen_candidate_queue")
    rows: list[dict[str, Any]] = []
    if queue_path is None or not queue_path.is_file():
        errors.append("Frozen candidate queue is missing")
    else:
        rows = load_jsonl(queue_path)
        counts = Counter(str(row.get("channel_id")) for row in rows)
        if len(rows) != 40 or dict(counts) != EXPECTED_CHANNEL_COUNTS:
            errors.append("Frozen candidate queue balance changed")
        ids = [str(row.get("candidate_id")) for row in rows]
        hosts = [str(row.get("candidate_identity", {}).get("normalized_host")) for row in rows]
        if len(ids) != len(set(ids)) or len(hosts) != len(set(hosts)):
            errors.append("Frozen candidate queue contains duplicate IDs or hosts")
        for row in rows:
            review = row.get("review_state", {})
            safety = row.get("safety", {})
            if (
                review.get("ground_truth_status") != "UNCERTAIN"
                or review.get("training_eligible") != "NO"
                or review.get("label_created") is not False
                or safety.get("wayback_queried") is not False
                or safety.get("live_domain_accessed") is not False
            ):
                errors.append("Frozen candidate queue state changed before availability query")
                break
    query = protocol.get("availability_query_contract", {})
    if query.get("endpoint") != "https://archive.org/wayback/available":
        errors.append("Wayback availability endpoint changed")
    if set(query.get("allowed_network_hosts", [])) != ALLOWED_ARCHIVE_HOSTS:
        errors.append("Allowed archive host set changed")
    if query.get("request_rate_per_second_maximum") != 1:
        errors.append("Wayback request-rate cap changed")
    if float(query.get("minimum_delay_seconds", 0)) < 1.0:
        errors.append("Wayback minimum request delay is too short")
    for key, expected in {
        "maximum_attempts_per_candidate": 1,
        "https_only": True,
        "automatic_external_redirect_following": False,
        "stop_on_http_429": True,
        "errors_are_not_interpreted_as_no_snapshot": True,
        "archived_page_download_allowed": False,
        "live_candidate_domain_access_allowed": False,
        "output_overwrite_allowed": False,
    }.items():
        if query.get(key) != expected:
            errors.append(f"Wayback query guard changed: {key}")
    return {
        "valid": not errors,
        "protocol": protocol,
        "queue_path": queue_path,
        "candidate_count": len(rows),
        "channel_counts": dict(Counter(str(row.get("channel_id")) for row in rows)),
        "errors": errors,
    }


def execute(protocol_path: Path) -> dict[str, Any]:
    validation = validate_protocol(protocol_path)
    if not validation["valid"]:
        raise ValueError(f"Protocol validation failed: {validation['errors']}")
    protocol = validation["protocol"]
    query_contract = protocol["availability_query_contract"]
    queue_path = validation["queue_path"]
    assert isinstance(queue_path, Path)
    output_path = Path(protocol["planned_output"]["path"])
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output_path}")
    rows = load_jsonl(queue_path)
    request_counter = [0]
    results: list[dict[str, Any]] = []
    stopped_on_429 = False
    for index, row in enumerate(rows):
        identity = row["candidate_identity"]
        base = {
            "candidate_id": row["candidate_id"],
            "channel_id": row["channel_id"],
            "channel_target_stratum": row["channel_target_stratum"],
            "candidate_host": identity["normalized_host"],
            "candidate_url": identity["candidate_url"],
            "query_timestamp": query_contract["target_timestamp"],
        }
        if stopped_on_429:
            results.append({
                **base,
                "queried": False,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": None,
                "error": "NOT_QUERIED_AFTER_HTTP_429_STOP",
            })
            continue
        url = availability_url(
            query_contract["endpoint"],
            identity["candidate_url"],
            query_contract["target_timestamp"],
        )
        try:
            payload = fetch_json(
                url,
                timeout_seconds=int(query_contract["timeout_seconds"]),
                delay_seconds=float(query_contract["minimum_delay_seconds"]),
                request_counter=request_counter,
            )
            result = parse_availability_response(payload)
            results.append({**base, "queried": True, **result, "error": None})
        except RateLimitStop as error:
            stopped_on_429 = True
            results.append({
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": "429",
                "error": f"{type(error).__name__}: {error}",
            })
        except Exception as error:  # preserve acquisition uncertainty exactly
            results.append({
                **base,
                "queried": True,
                "available": None,
                "snapshot_timestamp": None,
                "snapshot_url": None,
                "snapshot_http_status": None,
                "error": f"{type(error).__name__}: {error}",
            })
    unresolved = sum(row["error"] is not None for row in results)
    report = {
        "report_id": protocol["planned_output"]["report_id"],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE_ERRORS_PRESERVED",
        "protocol_path": str(protocol_path.resolve()),
        "protocol_sha256": sha256_file(protocol_path),
        "queue_path": str(queue_path.resolve()),
        "queue_sha256": sha256_file(queue_path),
        "requested_candidate_count": len(rows),
        "network_request_count": request_counter[0],
        "available_snapshot_count": sum(row["available"] is True for row in results),
        "unavailable_snapshot_count": sum(row["available"] is False for row in results),
        "unresolved_error_count": unresolved,
        "stopped_on_http_429": stopped_on_429,
        "capture_planning_ready": unresolved == 0,
        "results": results,
        "safety_contract": {
            "candidate_live_domain_access_operations": 0,
            "only_archive_availability_hosts_accessed": True,
            "archived_page_download_operations": 0,
            "candidate_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = validate_protocol(args.protocol)
        public = {key: value for key, value in result.items() if key != "protocol"}
        if isinstance(public.get("queue_path"), Path):
            public["queue_path"] = str(public["queue_path"])
        print(json.dumps(public, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1
    report = execute(args.protocol)
    print(json.dumps({key: report[key] for key in (
        "report_id", "status", "requested_candidate_count", "network_request_count",
        "available_snapshot_count", "unavailable_snapshot_count", "unresolved_error_count",
        "stopped_on_http_429", "capture_planning_ready"
    )}, ensure_ascii=False, indent=2))
    return 0 if report["capture_planning_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
