"""Verify the frozen exact-53 ready-channel capture execution release."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_RELEASE_V1"
PASS_STATUS = "PASS_FROZEN_EXACT_53_ARCHIVE_ONLY_CAPTURE_RELEASE"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return result


def verify(release_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        release = load(release_path)
        release_hash = sha256_file(release_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {"verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_RELEASE_QA_V1", "status": "FAIL", "errors": [str(error)]}
    if release.get("release_id") != RELEASE_ID or release.get("status") != "FROZEN_EXACT_53_ARCHIVE_ONLY_CAPTURE_SEPARATE_INVOCATION":
        errors.append("unexpected release identity or status")
    for item in release.get("tooling", []):
        path = ROOT / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            errors.append(f"tooling hash mismatch: {item['path']}")
    plan_item = release.get("inputs", {}).get("capture_plan", {})
    qa_item = release.get("inputs", {}).get("independent_plan_qa", {})
    try:
        plan_path, qa_path = Path(plan_item["path"]), Path(qa_item["path"])
        if sha256_file(plan_path) != plan_item["sha256"]:
            errors.append("capture plan hash mismatch")
        if sha256_file(qa_path) != qa_item["sha256"]:
            errors.append("capture plan QA hash mismatch")
        plan, qa = load(plan_path), load(qa_path)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        plan, qa = {}, {}
        errors.append(f"cannot read plan evidence: {error}")
    rows = list(plan.get("results", []))
    if plan.get("status") != "FROZEN_EXACT_53_ELIGIBLE_ONLY_RAW_WAYBACK_CAPTURE_PLAN" or len(rows) != 53:
        errors.append("capture plan is not exact eligible 53")
    if qa.get("status") != "PASS_EXACT_53_ELIGIBLE_CAPTURE_PLAN_SEPARATE_RELEASE_MAY_BE_PREPARED" or qa.get("decision", {}).get("capture_release_may_be_prepared") is not True:
        errors.append("capture plan QA did not pass")
    if qa.get("inputs", {}).get("plan_sha256") != plan_item.get("sha256"):
        errors.append("plan/QA hash binding mismatch")
    ordered = [row.get("availability_plan_id") for row in rows]
    if ordered != release.get("identity_contract", {}).get("ordered_availability_plan_ids"):
        errors.append("ordered identity contract changed")
    contract = release.get("execution_contract", {})
    expected_contract = {
        "allowed_network_hosts": ["web.archive.org"], "minimum_delay_seconds": 30.0,
        "maximum_attempts_per_snapshot": 1, "timeout_seconds": 30,
        "maximum_redirects": 3, "maximum_response_bytes": 26214400,
        "minimum_response_bytes": 1024, "required_content_type_prefix": "text/html",
        "raw_replay_modifier_required": True, "stop_on_any_error": True,
        "partial_journal_reserved_before_network": True, "automatic_resume_allowed": False,
        "output_overwrite_allowed": False, "separate_invocation_required": True,
    }
    for key, value in expected_contract.items():
        if contract.get(key) != value:
            errors.append(f"execution contract changed: {key}")
    try:
        if parse_time(str(contract["not_before"])) < parse_time(str(release["created_at"])):
            errors.append("not-before predates release creation")
    except (KeyError, ValueError) as error:
        errors.append(str(error))
    for index, row in enumerate(rows):
        url = str(row.get("requested_archive_url", ""))
        if not url.startswith("https://web.archive.org/web/") or "id_/" not in url:
            errors.append(f"invalid raw replay URL at row {index}")
        if Path(str(row.get("capture_path", ""))).exists():
            errors.append(f"capture target already exists at row {index}")
    output = Path(str(release.get("planned_output", {}).get("path", "")))
    output_states = [output, output.with_suffix(output.suffix + ".partial"), output.with_suffix(output.suffix + ".finalizing")]
    if require_output_absent and any(path.exists() for path in output_states):
        errors.append("capture output state already exists")
    decision = release.get("decision", {})
    if decision.get("capture_allowed_after_release_qa_in_separate_invocation") is not True:
        errors.append("capture gate not declared")
    for key in ("candidate_live_domain_access_allowed", "text_extraction_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"forbidden gate opened: {key}")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_RELEASE_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(release_path.resolve()), "sha256": release_hash},
        "checks": {"record_count": len(rows), "plan_hash_verified": not any("plan hash" in error for error in errors), "minimum_delay_seconds": contract.get("minimum_delay_seconds"), "not_before": contract.get("not_before"), "planned_output_absent": not any(path.exists() for path in output_states)},
        "decision": {"release_qa_passed": not errors, "execution_allowed_at_or_after_not_before": not errors, "candidate_live_domain_access_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
