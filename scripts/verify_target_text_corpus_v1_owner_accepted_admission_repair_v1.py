"""Recompute and verify the frozen owner-accepted admission-repair readiness result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.analyze_target_text_corpus_v1_owner_accepted_admission_repair_v1 import analyze
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify(config_path: Path, result_path: Path) -> dict[str, Any]:
    actual = load_object(result_path)
    expected = analyze(config_path)
    errors: list[str] = []
    if _canonical(actual) != _canonical(expected):
        errors.append("Readiness report differs from full recomputation")
    if actual.get("decision", {}).get("v1_core_admitted_records") != 0:
        errors.append("Readiness report prematurely admits V1-Core records")
    if actual.get("decision", {}).get("training_allowed") is not False:
        errors.append("Readiness report opens training")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_OWNER_ACCEPTED_ADMISSION_REPAIR_QA_V1",
        "status": "PASS_READINESS_REPORT_FULLY_RECOMPUTED" if not errors else "FAIL",
        "inputs": {"protocol_sha256": sha256_file(config_path), "report_sha256": sha256_file(result_path)},
        "checks": {"record_count": actual.get("population", {}).get("record_count"), "ordered_record_ids_sha256": actual.get("population", {}).get("ordered_record_ids_sha256"), "v1_core_admitted_records": actual.get("decision", {}).get("v1_core_admitted_records")},
        "decision": {"readiness_qa_passed": not errors, "repaired_manifest_allowed": False, "partial_channel_contribution_allowed": False, "training_allowed": False},
        "errors": errors,
        "safety_contract": {"network_operations": 0, "labels_changed": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite admission-repair QA")
    result = verify(args.config, args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
