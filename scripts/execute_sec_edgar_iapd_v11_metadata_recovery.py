"""Execute the separately frozen V11 metadata-recovery capture release."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.execute_sec_edgar_iapd_v11_supplemental_capture import fetch_archive
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from scripts.build_sec_edgar_iapd_v11_metadata_recovery_release import RELEASE_ID, RELEASE_QA_STATUS


USER_AGENT = "ISI-V11-Metadata-Recovery-Capture/1.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)"


def validate(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    release = load_object(release_path)
    qa = load_object(release_qa_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("unexpected metadata-recovery release identity")
    qa_release_sha256 = qa.get("release_sha256") or qa.get("release", {}).get("sha256")
    if qa.get("status") != RELEASE_QA_STATUS or qa_release_sha256 != sha256_file(release_path):
        errors.append("release QA/hash mismatch")
    plan_item = release.get("inputs", {}).get("recovery_plan", {})
    plan_path = Path(str(plan_item.get("path", "")))
    if sha256_file(plan_path) != plan_item.get("sha256"):
        errors.append("recovery plan hash mismatch")
    plan = load_object(plan_path)
    if plan.get("ordered_ids") != release.get("identity_contract", {}).get("ordered_ids") or plan.get("planned_capture_count") != 2:
        errors.append("recovery plan identity/count mismatch")
    report_path = Path(str(release.get("planned_output", {}).get("path", "")))
    if report_path.exists() or report_path.with_suffix(report_path.suffix + ".partial").exists():
        errors.append("recovery report target already exists")
    for row in plan.get("results", []):
        target = Path(str(row["capture_path"]))
        if target.exists():
            errors.append(f"recovery raw target already exists: {target}")
    if errors:
        raise ValueError(f"metadata-recovery execution validation failed: {errors}")
    return release, plan


def execute(release_path: Path, release_qa_path: Path, now: datetime | None = None) -> dict[str, Any]:
    release_for_gate = load_object(release_path)
    current = now or datetime.now(timezone.utc).astimezone()
    gate = datetime.fromisoformat(str(release_for_gate["execution_contract"]["not_before"]))
    if current < gate:
        raise PermissionError(f"metadata-recovery gate is closed for {(gate - current).total_seconds():.0f} seconds")
    release, plan = validate(release_path, release_qa_path)
    report_path = Path(str(release["planned_output"]["path"]))
    partial = report_path.with_suffix(report_path.suffix + ".partial")
    reservation = {"report_id": release["planned_output"]["report_id"], "status": "RESERVED_BEFORE_NETWORK_NON_RESUMABLE", "reserved_at": current.isoformat(), "release_sha256": sha256_file(release_path), "release_qa_sha256": sha256_file(release_qa_path), "planned_capture_count": len(plan["results"]), "network_operations_started": False, "automatic_resume_allowed": False}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(reservation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counter = [0]
    rows: list[dict[str, Any]] = []
    stopped = False
    contract = release["execution_contract"]
    for source in plan["results"]:
        base = {key: source[key] for key in ("availability_plan_id", "shortlist_id", "cohort", "candidate_host", "candidate_url", "snapshot_timestamp", "snapshot_url", "requested_archive_url", "capture_path")}
        if stopped:
            rows.append({**base, "outcome": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP", "final_archive_url": None, "redirect_count": None, "http_status": None, "content_type": None, "bytes": None, "sha256": None, "attempt_count": 0, "diagnostics": {}, "error": "NOT_ATTEMPTED_AFTER_HTTP_429_STOP"})
            continue
        try:
            payload, final_url, redirects, content_type, diagnostics = fetch_archive(source["requested_archive_url"], timeout_seconds=int(contract["timeout_seconds"]), delay_seconds=float(contract["minimum_delay_seconds"]), request_counter=counter, max_redirects=int(contract["maximum_redirects"]), user_agent=USER_AGENT)
            target = Path(source["capture_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(payload)
            rows.append({**base, "outcome": "CAPTURED", "final_archive_url": final_url, "redirect_count": redirects, "http_status": 200, "content_type": content_type, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "attempt_count": 1, "diagnostics": diagnostics, "error": None})
        except Exception as error:
            status = getattr(error, "code", None)
            if status == 429:
                stopped = True
            diagnostics = getattr(error, "diagnostics", {})
            rows.append({**base, "outcome": "FAILED", "final_archive_url": None, "redirect_count": None, "http_status": status, "content_type": None, "bytes": None, "sha256": None, "attempt_count": 1, "diagnostics": diagnostics, "error": f"{type(error).__name__}: {error}"})
    captured = sum(row["outcome"] == "CAPTURED" for row in rows)
    failed = sum(row["outcome"] == "FAILED" for row in rows)
    not_attempted = sum(row["outcome"] == "NOT_ATTEMPTED_AFTER_HTTP_429_STOP" for row in rows)
    report = {"report_id": release["planned_output"]["report_id"], "created_at": current.isoformat(), "status": "COMPLETE" if captured == len(rows) else "INCOMPLETE_FAILURES_PRESERVED", "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)}, "release_qa": {"path": str(release_qa_path.resolve()), "sha256": sha256_file(release_qa_path)}, "plan": release["inputs"]["recovery_plan"], "planned_capture_count": len(rows), "network_request_count": counter[0], "captured_count": captured, "captured_by_cohort": dict(Counter(row["cohort"] for row in rows if row["outcome"] == "CAPTURED")), "failed_count": failed, "not_attempted_count": not_attempted, "stopped_on_http_429": stopped, "results": rows, "safety_contract": {"candidate_live_domain_access_operations": 0, "only_web_archive_host_accessed": True, "raw_replay_modifier_used": True, "automatic_external_redirect_following": False, "labels_created": 0, "model_operations": 0, "training_allowed": False}}
    finalized = report_path.with_suffix(report_path.suffix + ".finalizing")
    if finalized.exists():
        raise FileExistsError("recovery finalization staging file exists")
    finalized.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finalized.replace(report_path)
    persisted = load_object(report_path)
    if persisted.get("status") != report.get("status") or persisted.get("results") != report.get("results") or partial.exists():
        raise RuntimeError("recovery report finalization readback mismatch")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release, plan = validate(args.release, args.release_qa)
        gate = datetime.fromisoformat(str(release["execution_contract"]["not_before"]))
        print(json.dumps({"valid": True, "planned_capture_count": len(plan["results"]), "seconds_until_not_before": max(0, round((gate - datetime.now(gate.tzinfo)).total_seconds())), "user_agent": USER_AGENT}, indent=2))
        return 0
    report = execute(args.release, args.release_qa)
    print(json.dumps({key: report[key] for key in ("report_id", "status", "planned_capture_count", "network_request_count", "captured_count", "failed_count", "not_attempted_count", "stopped_on_http_429")}, indent=2))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
