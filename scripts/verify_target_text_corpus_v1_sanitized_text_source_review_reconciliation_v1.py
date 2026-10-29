"""Verify source-review reconciliation without opening acquisition or model gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECONCILIATION = ROOT / "configs" / "target_text_corpus_v1_sanitized_text_source_review_reconciliation_v1.json"


def verify(path: Path = RECONCILIATION) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        target = ROOT / item["path"]
        if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")
    ids = [row["candidate_id"] for row in value["rows"]]
    if ids != [f"DISC_V1_{index:03d}" for index in range(1, 7)]:
        raise ValueError("Reconciliation identity/order mismatch")
    if any(row["fresh_v1_core_credit"] != 0 for row in value["rows"]):
        raise ValueError("A reviewed source received premature fresh-core credit")
    synthetic = [row for row in value["rows"] if row["reconciled_state"].startswith("ADVANCE_")]
    if len(synthetic) != 1 or synthetic[0]["candidate_id"] != "DISC_V1_005" or "SYNTHETIC" not in synthetic[0]["role"]:
        raise ValueError("Synthetic-only advance changed")
    summary = value["summary"]
    if summary != {"reviewed_sources":6,"real_world_acquisition_ready_sources":0,"synthetic_auxiliary_assessment_ready_sources":1,"held_sources":4,"rejected_sources":1,"fresh_v1_core_admitted_groups":0,"new_training_rows_authorized":0}:
        raise ValueError("Reconciliation totals mismatch")
    decision = value["decision"]
    if decision["synthetic_auxiliary_registration_may_be_prepared"] is not True:
        raise ValueError("Synthetic auxiliary next gate missing")
    for key in ("real_world_acquisition_release_may_be_prepared","candidate_live_domain_access_allowed","labeling_allowed","validation_or_test_opening_allowed","training_allowed"):
        if decision[key] is not False:
            raise ValueError(f"Safety gate opened: {key}")
    return {"status":"PASS_RECONCILIATION_ZERO_REAL_WORLD_ACQUISITION_READY","reviewed_sources":6}


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False))


if __name__ == "__main__":
    main()
