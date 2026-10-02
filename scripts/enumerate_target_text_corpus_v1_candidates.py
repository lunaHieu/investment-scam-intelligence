"""Build the complete four-channel Target Text Corpus V1 provenance queue offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_target_text_corpus_v1_schema_review_pilot import validate_candidate
from src.isi.curation.target_text_candidate_enumeration import (
    CHANNELS,
    enumerate_balanced_candidates,
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            records.append(value)
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_ready_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("status") != "READY_FOR_BALANCED_ENUMERATION":
        raise ValueError("prerequisite ledger is not ready for balanced enumeration")
    prerequisites = ledger.get("prerequisites", [])
    if not isinstance(prerequisites, list) or len(prerequisites) != 2:
        raise ValueError("prerequisite ledger must contain exactly two entries")
    by_id = {item.get("prerequisite_id"): item for item in prerequisites}
    expected = {"CFTC_RED_REFERENCE_ARTIFACT", "SEC_EDGAR_USER_AGENT_IDENTITY"}
    if set(by_id) != expected:
        raise ValueError("prerequisite ledger membership changed")
    if any(item.get("readiness") != "READY" for item in prerequisites):
        raise ValueError("all acquisition prerequisites must be READY")
    gate = ledger.get("release_gate", {})
    if gate != {
        "all_prerequisites_ready": True,
        "candidate_enumeration_allowed": True,
        "network_execution_allowed": False,
    }:
        raise ValueError("ledger does not release offline enumeration only")
    cftc_artifact = by_id["CFTC_RED_REFERENCE_ARTIFACT"].get("local_artifact", {})
    cftc_path = Path(str(cftc_artifact.get("path", "")))
    cftc_hash = str(cftc_artifact.get("sha256", ""))
    if (
        cftc_artifact.get("exists") is not True
        or not cftc_artifact.get("recorded_at")
        or not cftc_path.is_file()
        or not re.fullmatch(r"[a-f0-9]{64}", cftc_hash)
        or sha256_file(cftc_path) != cftc_hash
    ):
        raise ValueError("CFTC reference artifact is missing or not hash-registered")
    sec_artifact = by_id["SEC_EDGAR_USER_AGENT_IDENTITY"].get("local_artifact", {})
    sec_path = Path(str(sec_artifact.get("path", "")))
    if (
        sec_artifact.get("exists") is not True
        or not sec_artifact.get("recorded_at")
        or not sec_path.is_file()
        or sec_artifact.get("sha256") is not None
    ):
        raise ValueError("SEC private identity must exist locally without a public-ledger hash")
    try:
        sec_path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("SEC private identity must remain outside the public repository")
    private = load_json(sec_path)
    if set(private) != {"organization_or_project", "contact_email", "purpose"}:
        raise ValueError("SEC private identity field contract changed")
    if not all(str(value).strip() for value in private.values()):
        raise ValueError("SEC private identity fields must be non-empty")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(private["contact_email"])):
        raise ValueError("SEC private contact email is invalid")
    purpose = str(private["purpose"]).casefold()
    if "investment" not in purpose or "research" not in purpose:
        raise ValueError("SEC private purpose must identify this investment research project")


def write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    text = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-protocol", type=Path, required=True)
    parser.add_argument("--prerequisite-ledger", type=Path, required=True)
    parser.add_argument("--confirmed-regulator", type=Path, required=True)
    parser.add_argument("--confirmed-cftc", type=Path, required=True)
    parser.add_argument("--legitimate-iapd", type=Path, required=True)
    parser.add_argument("--legitimate-edgar", type=Path, required=True)
    parser.add_argument("--enumerated-at", required=True)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    existing = [str(path) for path in (args.queue_output, args.report_output) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen outputs: {existing}")
    validate_ready_ledger(load_json(args.prerequisite_ledger))
    protocol = load_json(args.pilot_protocol)
    wave = protocol["initial_enumeration_wave"]
    selection = protocol["selection_contract"]
    inputs = {
        "CONFIRMED_REGULATOR_LINKED_WEBSITE": load_jsonl(args.confirmed_regulator),
        "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE": load_jsonl(args.confirmed_cftc),
        "LEGITIMATE_REGISTER_LINKED_WEBSITE": load_jsonl(args.legitimate_iapd),
        "LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE": load_jsonl(args.legitimate_edgar),
    }
    if set(inputs) != set(CHANNELS):
        raise ValueError("CLI channel mapping changed")
    queue, report = enumerate_balanced_candidates(
        inputs,
        quotas=wave["quota_by_channel"],
        seed=selection["selection_seed"],
        wave_id=wave["wave_id"],
        enumerated_at=args.enumerated_at,
    )
    candidate_errors = {
        record["candidate_id"]: validate_candidate(record)
        for record in queue
        if validate_candidate(record)
    }
    if candidate_errors:
        raise ValueError(f"Generated candidates failed schema invariants: {candidate_errors}")
    args.queue_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl_atomic(args.queue_output, queue)
    temp_report = args.report_output.with_suffix(args.report_output.suffix + ".tmp")
    temp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_report.replace(args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
