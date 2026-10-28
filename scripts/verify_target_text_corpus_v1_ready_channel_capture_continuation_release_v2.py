"""Verify the exact-48 ready-channel capture continuation release."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASS_STATUS = "PASS_FROZEN_EXACT_48_CAPTURE_CONTINUATION_RELEASE"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(path: Path, require_output_absent: bool = True) -> dict:
    release = load(path)
    errors: list[str] = []
    if (
        release.get("release_id") != "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_RELEASE_V2"
        or release.get("status") != "FROZEN_EXACT_48_ROW_LOCAL_QUARANTINE_CAPTURE_CONTINUATION"
    ):
        errors.append("release identity changed")
    for item in release.get("tooling", []):
        tool_path = ROOT / item["path"]
        if not tool_path.is_file() or sha(tool_path) != item["sha256"]:
            errors.append(f"tooling hash mismatch: {item['path']}")
    plan_ref = release["inputs"]["continuation_plan"]
    qa_ref = release["inputs"]["independent_plan_qa"]
    plan_path, qa_path = Path(plan_ref["path"]), Path(qa_ref["path"])
    if sha(plan_path) != plan_ref["sha256"] or sha(qa_path) != qa_ref["sha256"]:
        errors.append("plan evidence hash mismatch")
    plan, qa = load(plan_path), load(qa_path)
    rows = plan.get("results", [])
    if len(rows) != 48 or plan.get("status") != "FROZEN_EXACT_48_NEVER_ATTEMPTED_ONLY_CAPTURE_PLAN":
        errors.append("plan is not exact 48")
    if (
        qa.get("status") != "PASS_EXACT_48_NEVER_ATTEMPTED_CONTINUATION_PLAN"
        or qa.get("plan", {}).get("sha256") != plan_ref["sha256"]
    ):
        errors.append("plan QA mismatch")
    if [row["availability_plan_id"] for row in rows] != release.get("identity_contract", {}).get("ordered_availability_plan_ids"):
        errors.append("identity order changed")
    if any(Path(row["capture_path"]).exists() for row in rows):
        errors.append("continuation target exists")
    contract = release.get("execution_contract", {})
    expected = {
        "minimum_delay_seconds": 30.0,
        "maximum_attempts_per_snapshot": 1,
        "continue_on_verified_row_local_response_error": True,
        "stop_on_provider_or_transport_error": True,
        "automatic_resume_allowed": False,
        "output_overwrite_allowed": False,
        "separate_invocation_required": True,
        "preserve_all_response_bytes_before_classification": True,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            errors.append(f"contract changed: {key}")
    try:
        if datetime.fromisoformat(contract["not_before"]) < datetime.fromisoformat(release["created_at"]):
            errors.append("not-before predates creation")
    except ValueError:
        errors.append("invalid timestamp")
    output = Path(release["planned_output"]["path"])
    states = [output, output.with_suffix(output.suffix + ".partial"), output.with_suffix(output.suffix + ".finalizing")]
    if require_output_absent and any(candidate.exists() for candidate in states):
        errors.append("output exists")
    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_CONTINUATION_RELEASE_QA_V2",
        "status": PASS_STATUS if not errors else "FAIL",
        "release": {"path": str(path.resolve()), "sha256": sha(path)},
        "checks": {
            "record_count": len(rows),
            "planned_output_absent": not any(candidate.exists() for candidate in states),
            "not_before": contract.get("not_before"),
            "row_local_quarantine_continuation": contract.get("continue_on_verified_row_local_response_error"),
        },
        "decision": {
            "execution_allowed_in_separate_invocation": not errors,
            "candidate_live_domain_access_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": {"network_operations": 0, "captures": 0, "labels": 0, "model": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
