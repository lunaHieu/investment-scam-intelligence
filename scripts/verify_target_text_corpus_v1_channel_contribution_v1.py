"""Independently reproduce a V1-Core channel contribution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_target_text_corpus_v1_channel_contribution_v1 import build
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify(contribution_path: Path, contract_path: Path, matrix_path: Path, candidate_manifest_path: Path, channel_id: str) -> dict[str, Any]:
    errors: list[str] = []
    actual = load_object(contribution_path)
    try:
        expected = build(contract_path, matrix_path, candidate_manifest_path, channel_id)
    except Exception as error:
        return {"verification_id": "ISI_TARGET_TEXT_CORPUS_V1_CHANNEL_CONTRIBUTION_QA_V1", "status": "FAIL", "errors": [f"Independent build failed: {type(error).__name__}: {error}"]}
    if canonical(actual) != canonical(expected):
        errors.append("Contribution differs from independent recomputation")
    return {"verification_id": "ISI_TARGET_TEXT_CORPUS_V1_CHANNEL_CONTRIBUTION_QA_V1", "status": "PASS_CHANNEL_CONTRIBUTION_INDEPENDENTLY_REPRODUCED" if not errors else "FAIL", "inputs": {"contribution_sha256": sha256_file(contribution_path), "contract_sha256": sha256_file(contract_path), "matrix_sha256": sha256_file(matrix_path), "candidate_manifest_sha256": sha256_file(candidate_manifest_path)}, "checks": {"channel_id": actual.get("channel_id"), "record_count": len(actual.get("record_ids", [])), "counts": actual.get("counts")}, "decision": {"contribution_qa_passed": not errors, "full_dataset_release_required": True, "training_allowed": False}, "errors": errors, "safety_contract": {"network_operations": 0, "model_operations": 0, "training_operations": 0}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contribution", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite contribution QA")
    result = verify(args.contribution, args.contract, args.matrix, args.candidate_manifest, args.channel_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
