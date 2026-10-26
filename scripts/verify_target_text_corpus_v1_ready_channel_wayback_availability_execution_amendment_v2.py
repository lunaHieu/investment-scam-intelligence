"""Verify B5 V2 coordination against A1's canonical-empty independent QA."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_result_v2 import (
    PASS_STATUS as A1_V2_PASS_STATUS,
    verify as verify_a1_v2,
)
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1 import (
    PASS_STATUS as B4_V1_PASS_STATUS,
    verify as verify_b4_v1,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


AMENDMENT_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_EXECUTION_AMENDMENT_V2"
PASS_STATUS = "PASS_B5_V2_CANONICAL_EMPTY_A1_NONBLOCKING_EXECUTION_AMENDMENT"
QA_ID = "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_WAYBACK_AVAILABILITY_EXECUTION_AMENDMENT_QA_V2"


def _path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def verify(amendment_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    root = amendment_path.resolve().parents[1]
    amendment = load_object(amendment_path)
    errors: list[str] = []
    if amendment.get("amendment_id") != AMENDMENT_ID:
        errors.append("Unexpected B5 V2 amendment identity")

    parent = amendment.get("parent_release", {})
    release_path = _path(root, str(parent.get("path", "")))
    if not release_path.is_file() or sha256_file(release_path) != parent.get("sha256"):
        errors.append("B5 parent release hash mismatch")
        release = {}
    else:
        release = load_object(release_path)
        release_check = verify_b4_v1(release_path, require_output_absent=require_output_absent)
        if release_check.get("status") != B4_V1_PASS_STATUS or release_check.get("errors"):
            errors.append("Frozen B4 V1 release no longer verifies")

    release_qa_item = amendment.get("parent_release_qa", {})
    release_qa_path = _path(root, str(release_qa_item.get("path", "")))
    if not release_qa_path.is_file() or sha256_file(release_qa_path) != release_qa_item.get("sha256"):
        errors.append("B5 parent release QA hash mismatch")
    else:
        release_qa = load_object(release_qa_path)
        if release_qa.get("status") != B4_V1_PASS_STATUS or release_qa.get("errors") != [] or release_qa.get("release", {}).get("sha256") != parent.get("sha256"):
            errors.append("B5 parent release QA is not authoritative PASS")

    evidence = amendment.get("a1_canonical_empty_evidence", {})
    evidence_paths: dict[str, Path] = {}
    for role, item in evidence.items():
        path = _path(root, str(item.get("path", "")))
        evidence_paths[role] = path
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"A1 canonical-empty evidence hash mismatch: {role}")
    required = {"owner_override", "owner_override_qa", "execution_report", "v1_result_qa", "v2_result_qa"}
    if set(evidence_paths) != required:
        errors.append("A1 canonical-empty evidence roles changed")
    elif not errors:
        recomputed = verify_a1_v2(
            evidence_paths["owner_override"], evidence_paths["owner_override_qa"],
            evidence_paths["execution_report"], evidence_paths["v1_result_qa"],
        )
        stored = load_object(evidence_paths["v2_result_qa"])
        if recomputed != stored or recomputed.get("status") != A1_V2_PASS_STATUS or recomputed.get("errors") != []:
            errors.append("A1 canonical-empty V2 QA does not reproduce")
        root_cause = recomputed.get("root_cause", {})
        if root_cause.get("network_failure") is not False or root_cause.get("rate_limit") is not False or root_cause.get("retry_needed") is not False:
            errors.append("A1 is not a terminal non-network canonical-empty outcome")

    coordination = amendment.get("coordination_contract", {})
    try:
        report = load_object(evidence_paths["execution_report"])
        report_time = datetime.fromisoformat(str(report["created_at"]))
        floor = datetime.fromisoformat(str(coordination["absolute_not_before_floor"]))
        effective = max(report_time + timedelta(seconds=int(coordination["inherited_cooldown_seconds"])), floor)
        if effective.isoformat() != coordination.get("effective_not_before"):
            errors.append("B5 V2 effective not-before is not independently reproduced")
    except (KeyError, ValueError, TypeError, OSError, json.JSONDecodeError) as error:
        effective = None
        errors.append(f"B5 V2 coordination timestamps are invalid: {error}")

    policy = amendment.get("retry_policy", {})
    if policy.get("universal_fixed_24h_retry_forbidden") is not True or policy.get("maximum_network_attempts_per_artifact_family") != 3 or policy.get("a1_identical_retry_allowed") is not False:
        errors.append("B5 V2 adaptive retry policy changed")
    for item in amendment.get("authoritative_tooling", []):
        path = _path(root, str(item.get("path", "")))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"B5 V2 tooling hash mismatch: {item.get('role')}")

    decision = amendment.get("decision", {})
    if decision.get("a1_canonical_empty_is_terminal_nonblocking") is not True or decision.get("b5_execution_allowed_at_or_after_effective_not_before") is not True:
        errors.append("B5 V2 coordination decision changed")
    for gate in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            errors.append(f"B5 V2 forbidden gate opened: {gate}")

    output = Path(str(release.get("planned_output", {}).get("path", "")))
    partial = output.with_suffix(output.suffix + str(release.get("planned_output", {}).get("partial_journal_suffix", ".partial")))
    if require_output_absent and (output.exists() or partial.exists()):
        errors.append("B5 result or partial already exists")
    return {
        "verification_id": QA_ID,
        "status": PASS_STATUS if not errors else "FAIL",
        "amendment": {"path": str(amendment_path.resolve()), "sha256": sha256_file(amendment_path)},
        "checks": {
            "plan_rows": release.get("execution_contract", {}).get("expected_candidate_count"),
            "a1_canonical_empty_v2_qa_reproduced": not any("canonical-empty" in error for error in errors),
            "a1_rate_limit": False,
            "a1_retry_needed": False,
            "effective_not_before": effective.isoformat() if effective else None,
            "output_absent": not output.exists() and not partial.exists(),
            "network_operations": 0,
        },
        "decision": {"amendment_qa_passed": not errors, "b5_execution_allowed_at_or_after_effective_not_before": not errors, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    result = verify(args.amendment, require_output_absent=not args.allow_existing_output)
    if args.output and result["status"] != "FAIL":
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite B5 V2 amendment QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
