"""Verify the bounded sanitized-text source-discovery release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / "configs" / "target_text_corpus_v1_sanitized_text_source_discovery_release_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_release(path: Path = DEFAULT_RELEASE, require_output_absent: bool = False) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    for item in value["inputs"]:
        target = ROOT / item["path"]
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            raise ValueError(f"Input hash mismatch: {item['path']}")

    queries = value["queries"]
    ids = [item["query_id"] for item in queries]
    texts = [item["query"] for item in queries]
    contract = value["execution_contract"]
    if len(queries) != 12 or len(set(ids)) != 12 or len(set(texts)) != 12:
        raise ValueError("Release must contain exactly 12 unique queries")
    if contract["maximum_search_queries"] != 12 or contract["maximum_shortlisted_sources"] > 20:
        raise ValueError("Discovery bounds changed")
    for key in ("source_download_allowed", "candidate_live_domain_access_allowed", "raw_html_retention_allowed", "dataset_embedded_link_following_allowed", "labeling_allowed", "model_operations_allowed"):
        if contract[key] is not False:
            raise ValueError(f"Forbidden capability enabled: {key}")
    if contract["no_overwrite"] is not True:
        raise ValueError("No-overwrite requirement removed")
    output = ROOT / value["planned_output"]
    if require_output_absent and output.exists():
        raise FileExistsError(f"Planned output already exists: {output}")
    return {"status":"PASS_RELEASE_VERIFIED","query_count":len(queries),"planned_output":str(output),"output_exists":output.exists()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify_release(args.release, require_output_absent=args.verify_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
