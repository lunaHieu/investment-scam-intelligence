"""Verify an explicit one-time owner override of only the A1 CDX timing gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1 import verify as verify_release
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


OVERRIDE_ID = "ISI_SEC_EDGAR_IAPD_WAYBACK_ALTERNATE_SNAPSHOT_CDX_OWNER_TIMING_OVERRIDE_V1"
PASS_STATUS = "PASS_EXPLICIT_OWNER_TIMING_ONLY_OVERRIDE_ONE_REQUEST_SAFETY_UNCHANGED"


def verify(override_path: Path, *, require_output_absent: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    override = load_object(override_path)
    root = override_path.resolve().parents[1]
    if override.get("override_id") != OVERRIDE_ID or override.get("status") != "FROZEN_EXPLICIT_OWNER_TIMING_ONLY_OVERRIDE_ONE_REQUEST":
        errors.append("Unexpected owner timing override identity/status")
    inputs = override.get("inputs", {})
    release_path = Path(inputs.get("frozen_release", {}).get("path", ""))
    release_qa_path = Path(inputs.get("frozen_release_qa", {}).get("path", ""))
    if not release_path.is_file() or sha256_file(release_path) != inputs.get("frozen_release", {}).get("sha256"):
        errors.append("Frozen A1 release hash mismatch")
    if not release_qa_path.is_file() or sha256_file(release_qa_path) != inputs.get("frozen_release_qa", {}).get("sha256"):
        errors.append("Frozen A1 release QA hash mismatch")
    if not errors:
        release_check = verify_release(release_path, require_output_absent=require_output_absent)
        release = load_object(release_path)
        release_qa = load_object(release_qa_path)
        if release_check.get("errors"):
            errors.append("Frozen A1 release no longer verifies")
        if release_qa.get("status") != release_check.get("status") or release_qa.get("errors") != [] or release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
            errors.append("Frozen A1 release QA is not authoritative PASS")
    else:
        release = {}
    for item in override.get("implementation", []):
        path = root / item.get("path", "")
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Owner override implementation hash mismatch: {item.get('role')}")
    timing = override.get("timing_override", {})
    try:
        authorized = datetime.fromisoformat(timing["authorized_at"])
        effective = datetime.fromisoformat(timing["effective_not_before"])
        original = datetime.fromisoformat(timing["original_not_before"])
        if authorized != effective or effective >= original:
            errors.append("Owner override timestamps do not describe an explicit early timing-only exception")
    except Exception as exc:
        errors.append(f"Invalid owner override timestamp: {type(exc).__name__}: {exc}")
    if release and timing.get("original_not_before") != release.get("cooldown_contract", {}).get("not_before"):
        errors.append("Owner override is not bound to the original A1 not_before")
    required_true = (
        "explicit_owner_authorization",
        "one_execution_only",
        "all_non_timing_safety_contracts_unchanged",
        "stop_on_http_429_unchanged",
        "no_overwrite_unchanged",
        "no_live_candidate_domain_access_unchanged",
        "no_archived_page_download_unchanged",
    )
    if any(timing.get(key) is not True for key in required_true):
        errors.append("Owner timing-only override weakened a required safeguard")
    if timing.get("scope") != "NOT_BEFORE_ONLY" or timing.get("maximum_logical_requests") != 1:
        errors.append("Owner override scope/request budget expanded")
    decision = override.get("decision", {})
    for key in ("candidate_live_domain_access_allowed", "archived_page_download_allowed", "capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "model_scoring_allowed", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"Owner override opened forbidden gate: {key}")
    return {
        "verification_id": "ISI_SEC_EDGAR_IAPD_WAYBACK_ALTERNATE_SNAPSHOT_CDX_OWNER_OVERRIDE_QA_V1",
        "status": PASS_STATUS if not errors else "FAIL",
        "override": {"path": str(override_path.resolve()), "sha256": sha256_file(override_path)},
        "checks": {
            "scope": timing.get("scope"),
            "original_not_before": timing.get("original_not_before"),
            "effective_not_before": timing.get("effective_not_before"),
            "maximum_logical_requests": timing.get("maximum_logical_requests"),
            "non_timing_safety_contracts_unchanged": not errors,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--override", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.override)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite owner timing override QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
