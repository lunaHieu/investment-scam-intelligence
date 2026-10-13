"""Verify the frozen Dataset V1-Core sampling matrix and its closed execution gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPECTED_MATRIX_ID = "ISI_TARGET_TEXT_CORPUS_V1_SAMPLING_MATRIX_V1"


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


def verify(matrix_path: Path) -> dict[str, Any]:
    matrix = load_object(matrix_path)
    root = matrix_path.resolve().parents[1]
    if matrix.get("matrix_id") != EXPECTED_MATRIX_ID:
        raise ValueError("Unexpected sampling-matrix ID")

    for item in matrix.get("basis", []):
        path = Path(str(item.get("path")))
        if not path.is_absolute():
            path = root / path
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Missing or changed basis: {item.get('role')}")

    development = matrix["cohorts"]["development"]["target_groups"]
    holdout = matrix["cohorts"]["untouched_external_holdout"]["target_groups"]
    if development != {"CONFIRMED": 120, "LEGITIMATE": 120, "total": 240}:
        raise ValueError("Development totals changed")
    if holdout != {"CONFIRMED": 30, "LEGITIMATE": 30, "total": 60}:
        raise ValueError("External-holdout totals changed")

    channels = matrix["channel_quotas"]
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for channel in channels:
        by_label[channel["target_status"]].append(channel)
        expected_reservoir = math.ceil(
            channel["total_accepted_group_quota"]
            / channel["pilot_candidate_to_decisive_yield"]
            * 1.25
        )
        if expected_reservoir != channel["planning_candidate_reservoir_with_25_percent_buffer"]:
            raise ValueError(f"Reservoir calculation changed: {channel['channel_id']}")
        capacity = channel["current_reference_pool_size"] >= expected_reservoir
        if capacity != channel["current_capacity_gate_passed"]:
            raise ValueError(f"Capacity decision changed: {channel['channel_id']}")
        if channel["artifact_acquisition"] != "WAYBACK_ARCHIVED_WEBSITE_HTML":
            raise ValueError("Capture stratum must be matched across labels")

    maximum_fraction = matrix["balance_contract"]["maximum_one_channel_fraction_per_label"]
    for label in ("CONFIRMED", "LEGITIMATE"):
        label_channels = by_label[label]
        if len(label_channels) < matrix["balance_contract"]["minimum_channels_per_label"]:
            raise ValueError(f"Too few channels for {label}")
        development_total = sum(row["development_accepted_group_quota"] for row in label_channels)
        holdout_total = sum(row["external_holdout_accepted_group_quota"] for row in label_channels)
        if development_total != development[label] or holdout_total != holdout[label]:
            raise ValueError(f"Channel totals do not match cohort totals for {label}")
        if max(row["development_accepted_group_quota"] for row in label_channels) / development_total > maximum_fraction:
            raise ValueError(f"Development channel fraction exceeded for {label}")
        if max(row["external_holdout_accepted_group_quota"] for row in label_channels) / holdout_total > maximum_fraction:
            raise ValueError(f"Holdout channel fraction exceeded for {label}")

    observed_capacity = Counter(row["current_capacity_gate_passed"] for row in channels)
    findings = matrix["capacity_findings"]
    if findings["channels_passing_current_candidate_reservoir_gate"] != observed_capacity[True]:
        raise ValueError("Passing-capacity count changed")
    if findings["channels_failing_current_candidate_reservoir_gate"] != observed_capacity[False]:
        raise ValueError("Failing-capacity count changed")
    blocked = sorted(row["channel_id"] for row in channels if not row["current_capacity_gate_passed"])
    if blocked != sorted(findings["blocked_channels"]):
        raise ValueError("Blocked-channel list changed")

    language = matrix["language_coverage"]
    if language["development_minimum_vietnamese_groups_per_label"] > language["development_minimum_non_english_groups_per_label"]:
        raise ValueError("Vietnamese development target exceeds non-English target")
    if language["external_holdout_minimum_vietnamese_groups_per_label"] > language["external_holdout_minimum_non_english_groups_per_label"]:
        raise ValueError("Vietnamese holdout target exceeds non-English target")

    decision = matrix["decision"]
    if not decision["matrix_structurally_valid"]:
        raise ValueError("Matrix did not pass structural validation")
    forbidden_open_gates = (
        "candidate_reservoir_capacity_gate_met",
        "language_supply_gate_met",
        "candidate_acquisition_release_allowed",
        "labeling_allowed",
        "training_allowed",
        "model_scoring_allowed",
    )
    if any(decision[key] is not False for key in forbidden_open_gates):
        raise ValueError("An execution or model gate was opened")
    if matrix["balance_contract"]["opened_pilot_records_count_toward_quotas"]:
        raise ValueError("Opened pilot cannot count toward fresh quotas")
    if matrix["balance_contract"]["mendeley_records_count_toward_quotas"]:
        raise ValueError("Mendeley cannot count toward target-corpus quotas")

    return {
        "matrix_id": matrix["matrix_id"],
        "development_groups": development["total"],
        "external_holdout_groups": holdout["total"],
        "channels": len(channels),
        "channels_capacity_ready": observed_capacity[True],
        "channels_capacity_blocked": observed_capacity[False],
        "acquisition_release_allowed": decision["candidate_acquisition_release_allowed"],
        "training_allowed": decision["training_allowed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.matrix), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
