"""Verify ScamBench and Vietnamese SMS missing-evidence checklists."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "configs" / "target_text_corpus_v1_real_world_source_missing_evidence_checklists_v1.json"


def verify(path: Path = CHECKLIST) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        if hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")
    sources = value["sources"]
    if [item["candidate_id"] for item in sources] != ["DISC_V1_001","DISC_V1_002"]:
        raise ValueError("Checklist source identity/order mismatch")
    evidence_ids = [row["evidence_id"] for source in sources for row in source["requirements"]]
    if evidence_ids != [f"SB{index:02d}" for index in range(1, 8)] + [f"VS{index:02d}" for index in range(1, 8)]:
        raise ValueError("Evidence identity/order mismatch")
    if any(row["blocking"] is not True for source in sources for row in source["requirements"]):
        raise ValueError("A required evidence item became nonblocking")
    summary = value["summary"]
    if summary != {"sources":2,"requirements":14,"fully_resolved":0,"acquisition_ready_sources":0,"fresh_v1_core_credit":0}:
        raise ValueError("Checklist totals mismatch")
    decision = value["decision"]
    if decision["bounded_metadata_evidence_release_may_be_prepared"] is not True:
        raise ValueError("Metadata evidence next gate missing")
    for key in ("author_contact_allowed_by_this_checklist","dataset_download_allowed","candidate_live_domain_access_allowed","labeling_allowed","training_allowed"):
        if decision[key] is not False:
            raise ValueError(f"Safety gate opened: {key}")
    return {"status":"PASS_MISSING_EVIDENCE_CHECKLISTS","sources":2,"requirements":14}


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False))


if __name__ == "__main__":
    main()
