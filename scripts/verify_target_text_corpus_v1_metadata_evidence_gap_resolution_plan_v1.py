"""Verify the metadata-evidence gap-resolution plan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "configs" / "target_text_corpus_v1_metadata_evidence_gap_resolution_plan_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    value = json.loads(PLAN.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        target = ROOT / item["path"]
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")
    lanes = value["lanes"]
    if [lane["lane_id"] for lane in lanes] != [
        "A_PUBLIC_FIRST_PARTY_METADATA", "B_GATED_USER_EVIDENCE", "C_PUBLISHER_CLARIFICATION"
    ]:
        raise ValueError("Lane identity or order changed")
    tasks = [task for lane in lanes for task in lane["tasks"]]
    if [task["task_id"] for task in tasks] != value["priority_order"] or len(tasks) != 7:
        raise ValueError("Exact seven-task priority order changed")
    if any(lane["execution_authorized_by_this_plan"] is not False for lane in lanes):
        raise ValueError("Planning artifact cannot authorize execution")
    covered = {target for task in tasks for target in task["targets"]}
    if not {"NX01","NX02","NX05","NX06","NX07","SB01","SB02","SB03","SB04","SB05","SB06","SB07","VS01","VS02","VS03","VS04","VS05","VS06"}.issubset(covered):
        raise ValueError("Known unresolved or partial evidence is not routed")
    decision = value["decision"]
    for key in ("lane_b_execution_allowed","lane_c_execution_allowed","dataset_download_allowed","candidate_live_domain_access_allowed","labeling_allowed","training_allowed"):
        if decision[key] is not False:
            raise ValueError(f"Closed gate opened: {key}")
    return {"status":"PASS_GAP_RESOLUTION_PLAN_VERIFIED","lanes":3,"tasks":7,"lane_a_tasks":4}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False))
