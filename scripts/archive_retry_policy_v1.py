"""Classify archive failures without turning every error into a 24-hour gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any


POLICY_ID = "ISI_ARCHIVE_RETRY_POLICY_V1"
MAX_NETWORK_ATTEMPTS_PER_ARTIFACT = 3
RATE_LIMIT_BACKOFF_SECONDS = (900, 3600, 21600, 86400)
TRANSIENT_BACKOFF_SECONDS = (300, 900, 3600)


def _time(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _retry_after(value: str | None, observed_at: datetime) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        seconds = int(text)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return observed_at + timedelta(seconds=max(0, seconds))


def _bounded_delay(schedule: tuple[int, ...], consecutive_failures: int) -> int:
    index = max(0, min(consecutive_failures - 1, len(schedule) - 1))
    return schedule[index]


def decide(
    *,
    failure_class: str,
    observed_at: str | datetime,
    network_attempts: int,
    consecutive_failures: int = 1,
    retry_after: str | None = None,
    artifact_required: bool = False,
    raw_bytes_persisted: bool = False,
    response_metadata_persisted: bool = False,
) -> dict[str, Any]:
    """Return a deterministic action; this function performs no network I/O."""
    now = _time(observed_at)
    normalized = failure_class.upper()
    base = {
        "policy_id": POLICY_ID,
        "failure_class": normalized,
        "observed_at": now.isoformat(),
        "network_attempts": network_attempts,
        "maximum_network_attempts": MAX_NETWORK_ATTEMPTS_PER_ARTIFACT,
        "project_blocked": False,
        "same_request_allowed": False,
        "not_before": None,
        "reason": None,
    }

    if normalized == "LOCAL_FINALIZATION":
        if raw_bytes_persisted and response_metadata_persisted:
            return {**base, "action": "OFFLINE_RECONCILE_NOW", "reason": "Network result is complete; only local finalization failed."}
        return {**base, "action": "OFFLINE_AUDIT_THEN_QUARANTINE", "reason": "Local failure is not evidence for another network request."}

    if normalized == "SUCCESS_METADATA_MISSING":
        action = "OPTIONAL_SUPPLEMENTAL_RECAPTURE" if artifact_required and network_attempts < MAX_NETWORK_ATTEMPTS_PER_ARTIFACT else "QUARANTINE_NONBLOCKING"
        return {**base, "action": action, "same_request_allowed": action == "OPTIONAL_SUPPLEMENTAL_RECAPTURE", "reason": "Persisted bytes remain usable evidence; metadata recovery is supplemental and cannot block the project."}

    if network_attempts >= MAX_NETWORK_ATTEMPTS_PER_ARTIFACT:
        return {**base, "action": "QUARANTINE_RETRY_BUDGET_EXHAUSTED", "reason": "Finite network retry budget exhausted."}

    if normalized == "HTTP_429":
        server_gate = _retry_after(retry_after, now)
        gate = server_gate or now + timedelta(seconds=_bounded_delay(RATE_LIMIT_BACKOFF_SECONDS, consecutive_failures))
        return {**base, "action": "RETRY_AFTER_RATE_LIMIT", "same_request_allowed": True, "not_before": gate.isoformat(), "reason": "Honor Retry-After when valid; otherwise use bounded exponential backoff."}

    if normalized in {"TIMEOUT", "DNS", "HTTP_5XX", "TRANSIENT_NETWORK"}:
        gate = now + timedelta(seconds=_bounded_delay(TRANSIENT_BACKOFF_SECONDS, consecutive_failures))
        return {**base, "action": "RETRY_TRANSIENT", "same_request_allowed": True, "not_before": gate.isoformat(), "reason": "Short bounded retry for a transient transport failure."}

    if normalized in {"HTTP_4XX", "INVALID_CONTENT", "EMPTY_RESULT", "PARSER_LIMITATION"}:
        return {**base, "action": "NO_IDENTICAL_RETRY_QUARANTINE", "reason": "A repeated identical request has no new evidence and is forbidden."}

    return {**base, "action": "MANUAL_CLASSIFICATION_REQUIRED_NONBLOCKING", "reason": "Unknown failures remain quarantined without blocking independent work."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failure-class", required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--network-attempts", type=int, required=True)
    parser.add_argument("--consecutive-failures", type=int, default=1)
    parser.add_argument("--retry-after")
    parser.add_argument("--artifact-required", action="store_true")
    parser.add_argument("--raw-bytes-persisted", action="store_true")
    parser.add_argument("--response-metadata-persisted", action="store_true")
    args = parser.parse_args()
    print(json.dumps(decide(**vars(args)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
