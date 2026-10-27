"""Recompute and verify the immutable Crimson primary-review readiness report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.audit_crimson_primary_review_readiness_v1 import PASS_STATUS, audit, sha256_file


QA_STATUS = "PASS_CRIMSON_PRIMARY_REVIEW_READINESS_FULLY_RECOMPUTED"


def verify(config_path: Path, report_path: Path) -> dict:
    errors: list[str] = []
    expected = audit(config_path)
    try:
        stored = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        stored = {}
        errors.append(f"Report loading failed: {type(exc).__name__}: {exc}")
    if expected.get("status") != PASS_STATUS:
        errors.append("Independent readiness recomputation did not pass")
    if stored != expected:
        errors.append("Stored readiness report differs from full recomputation")
    return {
        "verification_id": "ISI_CRIMSON_PRIMARY_REVIEW_READINESS_QA_V1",
        "status": QA_STATUS if not errors else "FAIL",
        "config": {"path": str(config_path.resolve()), "sha256": sha256_file(config_path)},
        "report": {"path": str(report_path.resolve()), "sha256": sha256_file(report_path) if report_path.is_file() else None},
        "counts": expected.get("counts", {}),
        "decision": {
            "readiness_report_verified": not errors,
            "human_review_complete": False,
            "labels_created": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "human_decisions_created": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.config, args.report)
    if args.output:
        partial = args.output.with_suffix(args.output.suffix + ".partial")
        if args.output.exists() or partial.exists():
            raise FileExistsError("Refusing to overwrite Crimson readiness QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == QA_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
