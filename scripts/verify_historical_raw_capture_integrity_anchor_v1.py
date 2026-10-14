"""Independently verify the historical raw-capture integrity anchor V1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANCHOR = REPO_ROOT / "registry" / "analyses" / "historical_raw_capture_integrity_anchor_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_evidence_sources(triage: dict[str, Any]) -> set[str]:
    return {
        item["source_document"]
        for row in triage["files"]
        for item in row["evidence"]
        if item["hash_matches"] and "usable_capture_view" not in item["source_document"]
    }


def verify(anchor_path: Path = DEFAULT_ANCHOR) -> dict[str, Any]:
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    triage_item = anchor["inputs"][0]
    triage_path = Path(triage_item["path"])
    if sha256_file(triage_path) != triage_item["sha256"]:
        raise ValueError("Triage artifact hash mismatch")
    triage = json.loads(triage_path.read_text(encoding="utf-8"))

    expected_sources = expected_evidence_sources(triage)
    anchored = {item["path"]: item["sha256"] for item in anchor["evidence_documents"]}
    if set(anchored) != expected_sources:
        raise ValueError("Anchor evidence-document set is not exact")
    for path_text, expected_hash in anchored.items():
        if sha256_file(Path(path_text)) != expected_hash:
            raise ValueError(f"Evidence document hash mismatch: {path_text}")

    covered = 0
    for row in triage["files"]:
        matching = [
            item
            for item in row["evidence"]
            if item["hash_matches"] and item["source_document"] in anchored
        ]
        if not matching:
            raise ValueError(f"Uncovered triage row: {row['relative_path']}")
        covered += 1

    findings = anchor["findings"]
    if findings["anchored_evidence_document_count"] != len(anchored):
        raise ValueError("Anchored evidence count mismatch")
    if findings["covered_previously_unanchored_raw_files"] != covered:
        raise ValueError("Covered raw-file count mismatch")
    decision = anchor["decision"]
    if decision["files_promoted"] != 0 or decision["training_allowed"]:
        raise ValueError("Anchor opens a prohibited downstream gate")
    if decision["validation_or_test_opening_allowed"] or decision["labeling_allowed"]:
        raise ValueError("Anchor opens validation/test or labeling")
    return {
        "status": "PASS_HISTORICAL_CAPTURE_INTEGRITY_ANCHOR_VERIFIED",
        "anchored_evidence_document_count": len(anchored),
        "covered_previously_unanchored_raw_files": covered,
        "files_promoted": 0,
        "training_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    args = parser.parse_args()
    print(json.dumps(verify(args.anchor), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
