"""Verify exact-48 continuation captures and quarantined raw response bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_capture_continuation_release_v2 import load, sha


def verify(release_path: Path, qa_path: Path, report_path: Path) -> dict:
    release, report = load(release_path), load(report_path)
    plan = load(Path(release["inputs"]["continuation_plan"]["path"]))
    errors: list[str] = []
    expected = {row["capture_plan_id"]: row for row in plan["results"]}
    actual = {row["capture_plan_id"]: row for row in report["results"]}
    if list(expected) != list(actual):
        errors.append("membership/order changed")
    captured = quarantined = 0
    for key, row in actual.items():
        capture_path = Path(row["capture_path"])
        if row["outcome"] == "CAPTURED":
            captured += 1
            if not capture_path.is_file() or capture_path.stat().st_size != row["bytes"] or sha(capture_path) != row["sha256"]:
                errors.append(f"capture byte/hash mismatch: {key}")
        elif row["outcome"] in {"QUARANTINED_ROW_LOCAL_RESPONSE", "FAILED_PROVIDER_OR_TRANSPORT"}:
            if capture_path.exists():
                errors.append(f"failed row created capture target: {key}")
            raw = row.get("raw_response_path")
            if raw:
                raw_path = Path(raw)
                if not raw_path.is_file() or raw_path.stat().st_size != row["bytes"] or sha(raw_path) != row["sha256"]:
                    errors.append(f"diagnostic byte/hash mismatch: {key}")
            if row["outcome"] == "QUARANTINED_ROW_LOCAL_RESPONSE":
                quarantined += 1
        elif capture_path.exists():
            errors.append(f"non-captured target exists: {key}")
    complete_population = report["not_attempted_count"] == 0 and report["failed_provider_or_transport_count"] == 0
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_RESULT_QA_V2",
        "status": "PASS_COMPLETE_48_POPULATION_WITH_QUARANTINES" if complete_population and not errors else "PASS_PARTIAL_PROVIDER_FAILURE_PRESERVED" if not errors else "FAIL",
        "inputs": {"release_sha256": sha(release_path), "release_qa_sha256": sha(qa_path), "report_sha256": sha(report_path)},
        "checks": {"planned": 48, "captured": captured, "quarantined_row_local": quarantined, "complete_population": complete_population, "byte_hashes_verified": not errors},
        "decision": {"combined_capture_reconciliation_may_be_prepared": complete_population and not errors, "automatic_retry_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = verify(args.release, args.release_qa, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
