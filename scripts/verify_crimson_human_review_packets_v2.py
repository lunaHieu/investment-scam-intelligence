"""Independently recompute and verify Crimson human-review task packets V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_crimson_human_review_packets_v2 import build_packets, load_jsonl, sha256_file


def verify(config_path: Path, output_root: Path | None = None) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected, expected_report = build_packets(config_path)
    root = output_root or Path(config["planned_outputs"]["root"])
    names = config["planned_outputs"]
    report_path = root / names["report"]
    if not report_path.is_file():
        raise ValueError("Crimson packet report is missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS_PACKETS_READY_NO_DECISIONS_CREATED":
        raise ValueError("Crimson packet report did not pass")
    if report.get("release", {}).get("sha256") != sha256_file(config_path):
        raise ValueError("Crimson packet report is not bound to the release")
    checked: dict[str, dict[str, Any]] = {}
    for key, expected_rows in expected.items():
        path = root / names[key]
        actual_rows = load_jsonl(path)
        if actual_rows != expected_rows:
            raise ValueError(f"Crimson packet content mismatch: {key}")
        recorded = report.get("outputs", {}).get(key, {})
        if recorded.get("sha256") != sha256_file(path) or recorded.get("record_count") != len(actual_rows):
            raise ValueError(f"Crimson packet hash/count mismatch: {key}")
        checked[key] = {"record_count": len(actual_rows), "sha256": sha256_file(path)}
    if report.get("counts") != expected_report["counts"]:
        raise ValueError("Crimson packet report counts changed")
    if report.get("human_decisions_created") != 0 or report.get("labels_created") != 0:
        raise ValueError("Crimson packet materialization created a decision or label")
    if report.get("training_eligible_records") != 0 or report.get("network_operations") != 0:
        raise ValueError("Crimson packet opened a training or network gate")
    return {
        "valid": True,
        "counts": report["counts"],
        "second_review_population": report["second_review_population"],
        "live_gap_count": report["live_gap_recomputed_from_current_decisions"],
        "human_decisions_created": 0,
        "labels_created": 0,
        "network_operations": 0,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.config, args.output_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
