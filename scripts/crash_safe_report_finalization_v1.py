"""Crash-safe promotion of a pre-network reservation into a final report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def finalize_reserved_report(report_path: Path, report: dict[str, Any]) -> None:
    """Atomically promote a report while ensuring no stale partial survives success.

    The reservation is replaced atomically by a complete report at the partial
    path, then that complete partial is renamed to the final path.  A crash can
    therefore leave either a reservation or a complete recoverable partial,
    never a final report plus a stale reservation.
    """
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    staging = report_path.with_suffix(report_path.suffix + ".finalizing")
    if report_path.exists() or staging.exists() or not partial.is_file():
        raise FileExistsError("Finalization requires one reservation, no final report, and no staging file")
    reservation = _load(partial)
    if reservation.get("status") != "RESERVED_BEFORE_NETWORK_NON_RESUMABLE":
        raise ValueError("Partial journal is not the expected pre-network reservation")
    staging.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if _load(staging) != report:
        raise RuntimeError("Finalization staging readback mismatch")
    staging.replace(partial)
    if _load(partial) != report:
        raise RuntimeError("Complete partial readback mismatch")
    partial.replace(report_path)
    if _load(report_path) != report or partial.exists() or staging.exists():
        raise RuntimeError("Atomic report promotion readback mismatch")


def promote_verified_complete_partial(report_path: Path) -> None:
    """Promote a caller-verified complete partial without any network access."""
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    if report_path.exists() or not partial.is_file():
        raise FileExistsError("Expected an absent final report and one complete partial")
    value = _load(partial)
    if value.get("status") not in {"COMPLETE", "INCOMPLETE_FAILURES_PRESERVED"} or not isinstance(value.get("results"), list):
        raise ValueError("Partial is a reservation or malformed report; offline promotion is forbidden")
    partial.replace(report_path)
