"""Verify the bounded three-branch public metadata-evidence release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / "configs" / "target_text_corpus_v1_metadata_evidence_release_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_release(path: Path = DEFAULT_RELEASE, require_output_absent: bool = False) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        target = ROOT / item["path"]
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")

    branches = value["branches"]
    if [branch["branch_id"] for branch in branches] != [
        "NEXVISION_METADATA", "SCAMBENCH_METADATA", "VIETNAMESE_SMS_METADATA"
    ]:
        raise ValueError("Exact branch order or identity changed")
    item_ids = [item["evidence_id"] for branch in branches for item in branch["evidence_items"]]
    if len(item_ids) != 21 or len(set(item_ids)) != 21:
        raise ValueError("Release must contain exactly 21 unique evidence items")
    if set(item_ids) != {*(f"NX{i:02}" for i in range(1, 8)), *(f"SB{i:02}" for i in range(1, 8)), *(f"VS{i:02}" for i in range(1, 8))}:
        raise ValueError("Evidence identities changed")

    queries = value["metadata_queries"]
    if len(queries) != 6 or len({q["query_id"] for q in queries}) != 6 or len({q["query"] for q in queries}) != 6:
        raise ValueError("Release must contain exactly six unique metadata queries")

    contract = value["execution_contract"]
    if contract["maximum_search_queries"] != 6 or contract["maximum_page_reads"] != 18:
        raise ValueError("Metadata bounds changed")
    if contract["maximum_followed_document_links_per_source"] != 3:
        raise ValueError("Per-source document-link bound changed")
    for branch in branches:
        for page in branch["initial_pages"]:
            if urlparse(page).hostname not in contract["allowed_authorities"]:
                raise ValueError(f"Initial page authority is not allowed: {page}")
    forbidden = (
        "dataset_download_allowed", "repository_clone_allowed", "raw_dataset_file_open_allowed",
        "raw_html_retention_allowed", "candidate_live_domain_access_allowed", "author_contact_allowed",
        "code_execution_allowed", "labeling_allowed", "validation_or_test_open_allowed", "model_operations_allowed",
    )
    for key in forbidden:
        if contract[key] is not False:
            raise ValueError(f"Forbidden capability enabled: {key}")
    if contract["primary_sources_only_for_evidence"] is not True or contract["metadata_claims_only"] is not True:
        raise ValueError("Primary-source metadata-only policy removed")
    if contract["no_overwrite"] is not True or contract["unresolved_policy"] != "RETAIN_UNRESOLVED_NO_INFERENCE":
        raise ValueError("Fail-closed result policy changed")

    output = ROOT / value["planned_output"]
    if require_output_absent and output.exists():
        raise FileExistsError(f"Planned output already exists: {output}")
    return {
        "status":"PASS_METADATA_EVIDENCE_RELEASE_VERIFIED",
        "branch_count":len(branches),
        "evidence_item_count":len(item_ids),
        "query_count":len(queries),
        "planned_output":str(output),
        "output_exists":output.exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify_release(args.release, require_output_absent=args.verify_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
