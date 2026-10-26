"""Execute V11 metadata recovery with atomic finalization and offline repair."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.crash_safe_report_finalization_v1 import finalize_reserved_report, promote_verified_complete_partial
from scripts.execute_sec_edgar_iapd_v11_metadata_recovery import fetch_archive, validate
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_result import verify as verify_result
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


USER_AGENT = "ISI-V11-Metadata-Recovery-Capture/2.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"
AMENDMENT_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_EXECUTION_AMENDMENT_V2"
ROOT = Path(__file__).resolve().parents[1]


def validate_amendment(amendment_path: Path, release_path: Path) -> dict[str, Any]:
    amendment = load_object(amendment_path)
    errors: list[str] = []
    if amendment.get("amendment_id") != AMENDMENT_ID:
        errors.append("unexpected execution amendment identity")
    parent = amendment.get("parent_release", {})
    if parent.get("sha256") != sha256_file(release_path) or parent.get("original_not_before_unchanged") is not True:
        errors.append("parent release hash or temporal preservation mismatch")
    for item in amendment.get("authoritative_tooling", []):
        path = ROOT / str(item.get("path", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"authoritative tooling hash mismatch: {item.get('role')}")
    contract = amendment.get("execution_contract", {})
    if contract.get("authoritative_executor_module") != "scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2" or contract.get("historical_v1_executor_forbidden") is not True or contract.get("acquisition_lane_blocks_project") is not False:
        errors.append("execution amendment contract changed")
    if errors:
        raise ValueError(f"metadata-recovery V2 amendment validation failed: {errors}")
    return amendment


def _base(source: dict[str, Any]) -> dict[str, Any]:
    return {key: source[key] for key in (
        "availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url",
        "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path",
    )}


def execute(release_path: Path, release_qa_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release_for_gate = load_object(release_path)
    current = now or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    gate = datetime.fromisoformat(str(release_for_gate["execution_contract"]["not_before"]))
    if current < gate:
        raise PermissionError(f"metadata-recovery gate is closed for {(gate - current).total_seconds():.0f} seconds")
    release, plan = validate(release_path, release_qa_path)
    report_path = Path(str(release["planned_output"]["path"]))
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    reservation = {
        "report_id": release["planned_output"]["report_id"],
        "status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE",
        "reserved_at": current.isoformat(),
        "release_sha256": sha256_file(release_path),
        "release_qa_sha256": sha256_file(release_qa_path),
        "planned_capture_count": len(plan["results"]),
        "network_operations_started": False,
        "automatic_resume_allowed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(reservation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counter = [0]
    rows: list[dict[str, Any]] = []
    stopped = False
    contract = release["execution_contract"]
    for source in plan["results"]:
        base = _base(source)
        if stopped:
            rows.append({**base, "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP", "final_archive_url": None, "redirect_count": None, "http_status": None, "content_type": None, "bytes": None, "sha256": None, "attempt_count": 0, "diagnostics": {}, "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP"})
            continue
        try:
            payload, final_url, redirects, content_type, diagnostics = fetch_archive(
                source["requested_archive_url"], timeout_seconds=int(contract["timeout_seconds"]),
                delay_seconds=float(contract["minimum_delay_seconds"]), request_counter=counter,
                max_redirects=int(contract["maximum_redirects"]), user_agent=USER_AGENT,
            )
            target = Path(source["capture_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            rows.append({**base, "outcome": "CAPTURED", "final_archive_url": final_url, "redirect_count": redirects, "http_status": 200, "content_type": content_type, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "attempt_count": 1, "diagnostics": diagnostics, "error": None})
        except Exception as error:
            status = getattr(error, "code", None)
            if status == 429:
                stopped = True
            rows.append({**base, "outcome": "FAILED", "final_archive_url": None, "redirect_count": None, "http_status": status, "content_type": None, "bytes": None, "sha256": None, "attempt_count": 1, "diagnostics": getattr(error, "diagnostics", {}), "error": f"{type(error).__name__}: {error}"})

    captured = sum(row["outcome"] == "CAPTURED" for row in rows)
    failed = sum(row["outcome"] == "FAILED" for row in rows)
    not_attempted = sum(row["outcome"] == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP" for row in rows)
    report = {
        "report_id": release["planned_output"]["report_id"], "created_at": current.isoformat(),
        "status": "COMPLETE" if captured == len(rows) else "INCOMPLETE_FAILURES_PRESERVED",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "release_qa": {"path": str(release_qa_path.resolve()), "sha256": sha256_file(release_qa_path)},
        "plan": release["inputs"]["recovery_plan"], "planned_capture_count": len(rows),
        "network_request_count": counter[0], "captured_count": captured,
        "captured_by_cohort": dict(Counter(row["cohort"] for row in rows if row["outcome"] == "CAPTURED")),
        "failed_count": failed, "not_attempted_count": not_attempted, "stopped_on_http_429": stopped,
        "results": rows,
        "safety_contract": {"candidate_live_domain_access_operations": 0, "only_web_archive_host_accessed": True, "raw_replay_modifier_used": True, "automatic_external_redirect_following": False, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }
    finalize_reserved_report(report_path, report)
    return report


def reconcile_finalization(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    """Finish a crash-interrupted local promotion; never performs network I/O."""
    release = load_object(release_path)
    report_path = Path(str(release["planned_output"]["path"]))
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    if report_path.exists() or not partial.is_file():
        raise FileExistsError("No uniquely recoverable complete partial is present")
    qa = verify_result(release_path, release_qa_path, partial)
    if qa.get("errors") or not str(qa.get("status", "")).startswith("PASS_"):
        raise ValueError("Partial is not an independently valid complete report; preserving it unchanged")
    promote_verified_complete_partial(report_path)
    final_qa = verify_result(release_path, release_qa_path, report_path)
    if final_qa != qa:
        raise RuntimeError("Offline finalization reconciliation changed verified content")
    return {"status": "PASS_OFFLINE_FINALIZATION_RECONCILED", "report_path": str(report_path), "network_operations": 0, "result_qa_status": qa["status"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--reconcile-finalization", action="store_true")
    args = parser.parse_args()
    validate_amendment(args.amendment, args.release)
    if args.reconcile_finalization:
        print(json.dumps(reconcile_finalization(args.release, args.release_qa), ensure_ascii=False, indent=2))
        return 0
    if args.verify_only:
        release, plan = validate(args.release, args.release_qa)
        gate = datetime.fromisoformat(str(release["execution_contract"]["not_before"]))
        print(json.dumps({"valid": True, "planned_capture_count": len(plan["results"]), "seconds_until_not_before": max(0, round((gate - datetime.now(gate.tzinfo)).total_seconds())), "user_agent": USER_AGENT, "atomic_finalization": True, "offline_reconciliation": True}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "network_request_count", "captured_count", "failed_count", "not_attempted_count", "stopped_on_http_429")}, indent=2))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
