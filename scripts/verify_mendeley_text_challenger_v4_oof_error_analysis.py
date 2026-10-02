"""Verify the frozen train-only V4 OOF error analysis and its closed gates."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analyze_mendeley_text_challenger_v4_oof_errors import (  # noqa: E402
    ANALYSIS_ID,
    EXPECTED_PROTOCOL_SHA256,
    grouped_rate_summary,
    load_jsonl,
    neighbor_summary,
    rate_summary,
)
from mendeley_text_baseline_v2_common import sha256_file  # noqa: E402


STATUS = "FROZEN_TRAIN_OOF_DIAGNOSTIC_COMPLETE_NO_TUNING"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def verify(report_path: Path) -> dict[str, Any]:
    report = load_json(report_path)
    errors: list[str] = []
    if report.get("analysis_id") != ANALYSIS_ID:
        errors.append("Unexpected analysis ID")
    if report.get("status") != STATUS:
        errors.append("Unexpected analysis status")
    if report.get("protocol", {}).get("sha256") != EXPECTED_PROTOCOL_SHA256:
        errors.append("Protocol checksum mismatch")

    for role, item in report.get("inputs", {}).items():
        path = Path(item.get("path", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Pinned input missing or changed: {role}")
    artifacts = report.get("artifacts", {})
    loaded_artifacts = {}
    for role in ("row_diagnostics", "review_queue"):
        item = artifacts.get(role, {})
        path = Path(item.get("path", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Output missing or changed: {role}")
            loaded_artifacts[role] = []
        else:
            loaded_artifacts[role] = load_jsonl(path)
            if len(loaded_artifacts[role]) != item.get("record_count"):
                errors.append(f"Output row count changed: {role}")

    rows = loaded_artifacts.get("row_diagnostics", [])
    queue = loaded_artifacts.get("review_queue", [])
    if len(rows) != 3916 or len({row.get("record_id") for row in rows}) != 3916:
        errors.append("Expected 3,916 unique row diagnostics")
    if len({row.get("split_group_id") for row in rows}) != 3783:
        errors.append("Expected 3,783 unique diagnostic groups")

    recomputed_overall = rate_summary(rows)
    if recomputed_overall != report.get("transition_summary"):
        errors.append("Overall transition summary does not reproduce")
    for key, report_key in (
        ("source_dataset", "by_source_dataset"),
        ("source_label", "by_source_label_value"),
        ("development_fold", "by_development_fold"),
        ("truncated_at_512", "by_truncated_at_512"),
        ("pre_truncation_token_bucket", "by_pre_truncation_token_bucket"),
    ):
        recomputed = grouped_rate_summary(rows, key)
        if report_key in ("by_truncated_at_512", "by_pre_truncation_token_bucket"):
            stored = report.get("truncation_diagnostic", {}).get(report_key)
        else:
            stored = report.get(report_key)
        if recomputed != stored:
            errors.append(f"Grouped diagnostic does not reproduce: {report_key}")

    source_label_rows = [
        {**row, "source_label_key": f"{row['source_dataset']}|label={row['source_label']}"}
        for row in rows
    ]
    if grouped_rate_summary(source_label_rows, "source_label_key") != report.get(
        "by_source_label"
    ):
        errors.append("Source-label diagnostic does not reproduce")
    source_truncation_rows = [
        {
            **row,
            "source_truncation_key": (
                f"{row['source_dataset']}|truncated_at_512="
                f"{str(row['truncated_at_512']).lower()}"
            ),
        }
        for row in rows
    ]
    if grouped_rate_summary(source_truncation_rows, "source_truncation_key") != report.get(
        "truncation_diagnostic", {}
    ).get("by_source_and_truncated_at_512"):
        errors.append("Source-truncation diagnostic does not reproduce")

    neighbor = report.get("nearest_neighbor_diagnostic", {})
    if neighbor_summary(rows) != neighbor.get("all"):
        errors.append("Overall nearest-neighbor diagnostic does not reproduce")
    for transition in ("both_correct", "e5_regression", "e5_recovery", "both_wrong"):
        recomputed = neighbor_summary(row for row in rows if row["transition"] == transition)
        if recomputed != neighbor.get("by_transition", {}).get(transition):
            errors.append(f"Nearest-neighbor transition diagnostic changed: {transition}")

    row_by_id = {row.get("record_id"): row for row in rows}
    for row in rows:
        neighbor_row = row_by_id.get(row.get("nearest_neighbor_record_id"))
        if neighbor_row is None:
            errors.append(f"Unknown nearest-neighbor ID: {row.get('record_id')}")
            break
        if neighbor_row.get("split_group_id") == row.get("split_group_id"):
            errors.append(f"Nearest neighbor shares split group: {row.get('record_id')}")
            break

    if len(queue) != 60 or len({row.get("split_group_id") for row in queue}) != 60:
        errors.append("Review queue must contain 60 unique groups")
    queue_strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in queue:
        queue_strata[f"{row.get('transition')}|{row.get('source_dataset')}"] .append(row)
        diagnostic = row_by_id.get(row.get("record_id"))
        if diagnostic is None:
            errors.append(f"Unknown queue record: {row.get('record_id')}")
            break
        for key in (
            "source_dataset",
            "source_label",
            "development_fold",
            "split_group_id",
            "transition",
            "pre_truncation_token_count",
            "truncated_at_512",
            "nearest_neighbor_record_id",
        ):
            if row.get(key) != diagnostic.get(key):
                errors.append(f"Queue field mismatch {key}: {row.get('record_id')}")
                break
    if set(queue_strata) != {
        f"{transition}|{source}"
        for transition in ("e5_regression", "e5_recovery", "both_wrong")
        for source in (
            "cresci_stock_2018",
            "phishing",
            "spam_email",
            "twitter_bot_detection",
        )
    } or any(len(items) != 5 for items in queue_strata.values()):
        errors.append("Review queue does not contain five records per predeclared stratum")
    for items in queue_strata.values():
        if len({row["split_group_id"] for row in items}) != len(items):
            errors.append("Review queue repeats a group within a stratum")
            break

    quality = report.get("quality_gates", {})
    if not quality or not all(value is True for value in quality.values()):
        errors.append("One or more analysis quality gates failed")
    safety = report.get("safety_contract", {})
    for key, expected in {
        "new_embedding_operations": 0,
        "encoder_forward_passes": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
        "validation_rows_used": 0,
        "test_rows_used": 0,
        "external_rows_used": 0,
        "labels_changed": 0,
        "training_eligibility_changes": 0,
        "model_selection_changes": 0,
        "deployment_allowed": False,
    }.items():
        if safety.get(key) != expected:
            errors.append(f"Safety contract mismatch: {key}")

    unexpected_validation_files = sorted(
        str(path)
        for path in report_path.parent.parent.rglob("*validation*")
        if path.is_file()
    )
    if unexpected_validation_files:
        errors.append("Validation-named artifacts exist under challenger V4 output root")

    return {
        "analysis_id": report.get("analysis_id"),
        "valid": not errors,
        "status": report.get("status"),
        "row_count": len(rows),
        "review_queue_count": len(queue),
        "transition_counts": recomputed_overall.get("transition_counts"),
        "validation_opened": False,
        "model_fit_operations": 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
