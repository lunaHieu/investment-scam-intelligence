"""Verify the proposed NexVision synthetic-only source addendum."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDENDUM = ROOT / "configs" / "target_text_corpus_v1_nexvision_synthetic_auxiliary_source_registration_addendum_v1.json"


def verify(path: Path = ADDENDUM) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        if hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")
    source = value["proposed_source"]
    if source["source_type"] != "synthetic_dataset" or source["default_evidence_level"] != "SYNTHETIC_ONLY" or source["gold_eligible"] is not False:
        raise ValueError("Synthetic-only source semantics changed")
    limits = value["role_limits"]
    if limits["fresh_v1_core_credit"] != 0:
        raise ValueError("Synthetic source received fresh-core credit")
    for key, item in limits.items():
        if key != "fresh_v1_core_credit" and item is not False:
            raise ValueError(f"Synthetic role limit opened: {key}")
    security = value["security_contract"]
    for key in ("repository_clone_allowed","code_execution_allowed","html_or_javascript_intake_allowed","archive_intake_allowed","candidate_live_domain_access_allowed"):
        if security[key] is not False:
            raise ValueError(f"Security gate opened: {key}")
    if security["malware_or_pua_policy"] != "ABANDON_BATCH_NO_RESTORE_NO_WHITELIST":
        raise ValueError("Malware abandonment policy changed")
    decision = value["decision"]
    if decision["metadata_evidence_release_may_be_prepared"] is not True:
        raise ValueError("Next metadata-evidence gate missing")
    for key in ("source_registry_mutation_allowed","dataset_acquisition_release_may_be_prepared","source_download_allowed","labeling_allowed","training_allowed"):
        if decision[key] is not False:
            raise ValueError(f"Decision gate opened: {key}")
    return {"status":"PASS_PROPOSED_SYNTHETIC_SOURCE_ADDENDUM","source_id":source["source_id"],"fresh_v1_core_credit":0}


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False))


if __name__ == "__main__":
    main()
