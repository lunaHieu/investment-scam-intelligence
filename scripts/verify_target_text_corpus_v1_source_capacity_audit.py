"""Verify the frozen Dataset V1-Core source-capacity audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_AUDIT_ID = "ISI_TARGET_TEXT_CORPUS_V1_SOURCE_CAPACITY_AUDIT_V1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify(audit_path: Path) -> dict[str, Any]:
    audit = load_object(audit_path)
    if audit.get("audit_id") != EXPECTED_AUDIT_ID:
        raise ValueError("Unexpected source-capacity audit ID")
    root = audit_path.resolve().parents[1]
    loaded: dict[str, dict[str, Any]] = {}
    for item in audit.get("basis", []):
        path = resolve(root, item.get("path"))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Missing or changed audit basis: {item.get('role')}")
        if path.suffix == ".json":
            loaded[item["role"]] = load_object(path)

    cftc = loaded["cftc_normalization_report"]
    crosswalk = loaded["sec_edgar_crosswalk_report"]
    edgar = loaded["sec_edgar_normalization_report"]
    existing = loaded["existing_channel_normalization_report"]
    findings = {row["channel_id"]: row for row in audit["channel_findings"]}

    if findings["CONFIRMED_REGULATOR_LINKED_WEBSITE"]["current_unique_reference_hosts"] != existing["outputs"]["confirmed_regulator"]["unique_host_count"]:
        raise ValueError("Regulator-linked host capacity changed")
    if findings["CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE"]["current_unique_reference_hosts"] != cftc["quality"]["unique_normalized_hosts"]:
        raise ValueError("CFTC host capacity changed")
    if findings["LEGITIMATE_REGISTER_LINKED_WEBSITE"]["current_unique_reference_hosts"] != existing["outputs"]["legitimate_iapd"]["unique_host_count"]:
        raise ValueError("IAPD host capacity changed")
    if findings["LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE"]["current_unambiguous_crosswalk_pool"] != crosswalk["quality"]["unambiguous_pool_count"]:
        raise ValueError("EDGAR crosswalk capacity changed")
    if findings["LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE"]["current_independently_approved_hosts"] != edgar["outputs"]["edgar_normalized"]["unique_host_count"]:
        raise ValueError("EDGAR approved capacity changed")

    expected_gaps = {
        "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": "capacity_gap",
        "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": "crosswalk_capacity_gap",
    }
    for channel_id, gap_key in expected_gaps.items():
        row = findings[channel_id]
        current_key = (
            "current_unique_reference_hosts"
            if channel_id.startswith("CONFIRMED")
            else "current_unambiguous_crosswalk_pool"
        )
        if row[gap_key] != row["planning_candidate_reservoir"] - row[current_key]:
            raise ValueError(f"Capacity gap changed: {channel_id}")

    decisions = audit["decision"]
    forbidden_open = (
        "existing_four_channel_matrix_executable_at_scale",
        "cftc_automatic_replenishment_allowed",
        "sec_bulk_download_allowed_by_this_audit",
        "new_candidate_enumeration_allowed",
        "new_capture_allowed",
        "labeling_allowed",
        "training_allowed",
    )
    if any(decisions[key] is not False for key in forbidden_open):
        raise ValueError("Audit opened a prohibited execution or model gate")
    if decisions["source_or_channel_amendment_required"] is not True:
        raise ValueError("Source/channel amendment requirement was removed")

    observations = {item["source_id"]: item for item in audit["official_source_observations"]}
    if "not verified" not in observations["dfpi_crypto_scam_tracker"]["operational_limit"]:
        raise ValueError("DFPI complaint-label limitation missing")
    if "not authorize generic automated" not in observations["cftc_red_list"]["operational_limit"]:
        raise ValueError("CFTC automated-scraping prohibition missing")
    if "not an automatic LEGITIMATE" not in observations["vietnam_official_exchange_issuer_profiles"]["operational_limit"]:
        raise ValueError("Vietnamese registry-as-legitimacy prohibition missing")

    return {
        "audit_id": audit["audit_id"],
        "channels_audited": len(findings),
        "channels_capacity_pass": sum("PASS" in row["capacity_status"] for row in findings.values()),
        "channels_capacity_fail": sum("FAIL" in row["capacity_status"] for row in findings.values()),
        "source_or_channel_amendment_required": decisions["source_or_channel_amendment_required"],
        "candidate_enumeration_allowed": decisions["new_candidate_enumeration_allowed"],
        "training_allowed": decisions["training_allowed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.audit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
