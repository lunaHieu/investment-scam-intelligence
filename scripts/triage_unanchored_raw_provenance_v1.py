"""Triage uncovered raw files against pre-existing, unanchored capture evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.audit_raw_cross_registry_provenance_v1 import (
    RAW_ROOT,
    iter_hash_pinned_paths,
    sha256_file,
)


DATA_ROOT = Path(r"D:\nckh 2026-2027\ISI_Data")
PRIOR_AUDIT = DATA_ROOT / "derived" / "project_state_audit_v1" / "raw_cross_registry_provenance_audit_v1.json"
PRIOR_AUDIT_SHA256 = "3cb325bd0a414cd348a8138c86e09528359b2cc1e097f8ee631619dae9b52f52"


def evidence_documents(data_root: Path = DATA_ROOT) -> list[Path]:
    tokens = ("capture", "acquisition", "manifest", "artifact_audit")
    paths: list[Path] = []
    for branch in (data_root / "derived", data_root / "curated"):
        if not branch.is_dir():
            continue
        for path in branch.rglob("*.json"):
            if "project_state_audit_v1" in path.parts:
                continue
            if any(token in path.name.casefold() for token in tokens):
                paths.append(path.resolve())
    return sorted(set(paths), key=lambda item: str(item).casefold())


def uncovered_paths(prior_audit: dict[str, Any], raw_root: Path) -> list[Path]:
    return [
        (raw_root / item["relative_path"]).resolve()
        for item in prior_audit["raw_inventory"]
        if item["category"] == "NO_HASH_PINNED_CHAIN_FOUND"
    ]


def build_report(
    prior_audit_path: Path = PRIOR_AUDIT,
    prior_audit_sha256: str = PRIOR_AUDIT_SHA256,
    data_root: Path = DATA_ROOT,
    raw_root: Path = RAW_ROOT,
) -> dict[str, Any]:
    actual_prior_hash = sha256_file(prior_audit_path)
    if actual_prior_hash != prior_audit_sha256:
        raise ValueError("Prior provenance audit hash mismatch")
    prior = json.loads(prior_audit_path.read_text(encoding="utf-8"))
    targets = uncovered_paths(prior, raw_root)
    target_set = set(targets)
    evidence_by_target: dict[Path, list[dict[str, Any]]] = {target: [] for target in targets}
    parse_failures: list[dict[str, str]] = []
    scanned = evidence_documents(data_root)
    hash_cache: dict[Path, str] = {}

    for source in scanned:
        try:
            data = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_failures.append({"path": str(source), "error": type(exc).__name__})
            continue
        source_hash = sha256_file(source)
        for path_key, target, hash_key, expected in iter_hash_pinned_paths(data, Path.cwd()):
            target = target.resolve()
            if target not in target_set:
                continue
            if target not in hash_cache:
                hash_cache[target] = sha256_file(target)
            evidence_by_target[target].append(
                {
                    "source_document": str(source),
                    "source_document_sha256": source_hash,
                    "path_key": path_key,
                    "hash_key": hash_key,
                    "expected_sha256": expected,
                    "actual_sha256": hash_cache[target],
                    "hash_matches": expected == hash_cache[target],
                    "anchor_state": "PRE_EXISTING_LOCAL_EVIDENCE_NOT_GIT_ROOTED",
                }
            )

    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for target in targets:
        evidence = evidence_by_target[target]
        matching = [item for item in evidence if item["hash_matches"]]
        conflicting = [item for item in evidence if not item["hash_matches"]]
        if matching:
            category = "MATCHING_UNANCHORED_HASH_EVIDENCE"
        elif conflicting:
            category = "CONFLICTING_UNANCHORED_HASH_EVIDENCE"
        else:
            category = "NO_LOCAL_HASH_EVIDENCE_FOUND"
        counts[category] += 1
        rows.append(
            {
                "relative_path": target.relative_to(raw_root).as_posix(),
                "byte_count": target.stat().st_size,
                "category": category,
                "matching_evidence_count": len(matching),
                "conflicting_evidence_count": len(conflicting),
                "evidence": evidence,
            }
        )

    return {
        "triage_id": "ISI_UNANCHORED_RAW_PROVENANCE_TRIAGE_V1",
        "status": "PASS_GAPS_CLASSIFIED_NO_PROMOTION",
        "verification_mode": "READ_ONLY_OFFLINE_PRE_EXISTING_EVIDENCE_DISCOVERY",
        "input": {
            "prior_audit_path": str(prior_audit_path),
            "prior_audit_sha256": actual_prior_hash,
            "uncovered_file_count": len(targets),
        },
        "scope": {
            "evidence_document_count": len(scanned),
            "parse_failure_count": len(parse_failures),
            "allowed_filename_tokens": ["capture", "acquisition", "manifest", "artifact_audit"],
            "model_validation_test_artifacts_opened": 0,
        },
        "summary": {
            "matching_unanchored_hash_evidence_files": counts["MATCHING_UNANCHORED_HASH_EVIDENCE"],
            "conflicting_unanchored_hash_evidence_files": counts["CONFLICTING_UNANCHORED_HASH_EVIDENCE"],
            "no_local_hash_evidence_found_files": counts["NO_LOCAL_HASH_EVIDENCE_FOUND"],
        },
        "parse_failures": parse_failures,
        "files": rows,
        "decision": {
            "files_promoted": 0,
            "provenance_manufactured": False,
            "training_allowed": False,
            "validation_or_test_opening_allowed": False,
            "labeling_allowed": False,
            "next_gate": "Independently verify and explicitly register only pre-existing matching evidence documents; quarantine conflicting or evidence-free files.",
        },
        "safety_contract": {
            "network_operations": 0,
            "raw_file_modifications": 0,
            "labels_created": 0,
            "model_operations": 0,
            "validation_or_test_openings": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite unanchored provenance triage")
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({key: report[key] for key in ("triage_id", "status", "input", "scope", "summary", "decision")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
