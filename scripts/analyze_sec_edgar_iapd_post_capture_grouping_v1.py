"""Run label-free opened-cohort exclusion and disjoint grouping offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_grouping_release_v1 import RELEASE_ID
from scripts.build_target_text_corpus_v1_post_capture_grouping import (
    component_map,
    group_id,
    is_near_duplicate,
    load_opened_texts,
    shingles,
    similarity,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


RELEASE_QA_STATUS = "PASS_OFFLINE_GROUPING_RELEASE"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def host_sha256(value: str) -> str:
    normalized = value.casefold().rstrip(".")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    if release.get("release_id") != RELEASE_ID:
        raise ValueError("Unexpected grouping release identity")
    if release_qa.get("status") != RELEASE_QA_STATUS or release_qa.get("release", {}).get("sha256") != sha256_file(release_path):
        raise ValueError("Grouping release QA status or binding mismatch")
    if release_qa.get("decision", {}).get("offline_grouping_allowed") is not True:
        raise PermissionError("Offline grouping gate is closed")
    for role, item in release["inputs"].items():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError(f"Grouping input changed: {role}")
    manifest = read_jsonl(Path(release["inputs"]["exact_text_manifest"]["path"]))
    if len(manifest) != release["inputs"]["exact_text_manifest"]["record_count"]:
        raise ValueError("Exact-text manifest population changed")
    ids = [str(row["record_id"]) for row in manifest]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate exact-text record ID")
    opened_path = Path(release["inputs"]["opened_external_exclusion_index"]["path"])
    opened = load_object(opened_path)
    opened_by_key = {row["record_exclusion_key"]: row for row in opened["records"]}
    opened_texts = load_opened_texts(opened, release_path.resolve().parents[1])
    if set(opened_by_key) != set(opened_texts):
        raise ValueError("Opened text/index membership mismatch")
    method = release["method"]
    opened_shingles = {key: shingles(text, method["word_shingle_size"]) for key, text in opened_texts.items()}
    opened_capture: dict[str, list[str]] = defaultdict(list)
    opened_text_hash: dict[str, list[str]] = defaultdict(list)
    opened_host: dict[str, list[str]] = defaultdict(list)
    for key, row in opened_by_key.items():
        opened_capture[row["capture_sha256"]].append(key)
        opened_text_hash[row["text_sha256"]].append(key)
        opened_host[row["normalized_host_sha256"]].append(key)

    passed = [row for row in manifest if row["minimum_content_passed"]]
    by_id = {str(row["record_id"]): row for row in manifest}
    text_by_id: dict[str, str] = {}
    shingle_by_id: dict[str, set[tuple[str, ...]]] = {}
    for row in passed:
        path = Path(row["text_path"])
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != row["text_sha256"]:
            raise ValueError(f"Candidate text hash mismatch: {row['record_id']}")
        text = payload.decode("utf-8")
        text_by_id[row["record_id"]] = text
        shingle_by_id[row["record_id"]] = shingles(text, method["word_shingle_size"])

    candidate_ids = sorted(text_by_id)
    edges: list[tuple[str, str]] = []
    near_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, left in enumerate(candidate_ids):
        left_row = by_id[left]
        for right in candidate_ids[index + 1:]:
            right_row = by_id[right]
            jaccard, containment, shorter = similarity(shingle_by_id[left], shingle_by_id[right])
            near = is_near_duplicate(jaccard, containment, shorter, method)
            exact_host = host_sha256(left_row["candidate_host"]) == host_sha256(right_row["candidate_host"])
            exact_text = left_row["text_sha256"] == right_row["text_sha256"]
            if exact_host or exact_text or near:
                edges.append((left, right))
            if near:
                near_hits[left].append({"record_id": right, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter})
                near_hits[right].append({"record_id": left, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter})
    components = component_map(candidate_ids, edges)
    cross_cohort_groups: dict[str, list[str]] = {}
    for candidate_id in candidate_ids:
        members = components[candidate_id]
        cohorts = {by_id[member]["cohort"] for member in members}
        if len(cohorts) > 1:
            cross_cohort_groups[group_id("TTCX", members)] = members

    records: list[dict[str, Any]] = []
    for row in manifest:
        record_id = row["record_id"]
        if not row["minimum_content_passed"]:
            routing = "NOT_REVIEWABLE_BELOW_MINIMUM"
            technical_group = None
            exact_capture_hits: list[str] = []
            exact_text_hits: list[str] = []
            host_hits: list[str] = []
            opened_near: list[dict[str, Any]] = []
            cross_collision = False
        else:
            members = components[record_id]
            technical_group = {"transitive_exclusion_group_id": group_id("TTCX", members), "members": members, "semantics": "PROVISIONAL_EXCLUSION_CONTROL_ONLY"}
            exact_capture_hits = sorted(opened_capture.get(row["raw_capture_sha256"], []))
            exact_text_hits = sorted(opened_text_hash.get(row["text_sha256"], []))
            host_hits = sorted(opened_host.get(host_sha256(row["candidate_host"]), []))
            opened_near = []
            for opened_key, opened_set in opened_shingles.items():
                jaccard, containment, shorter = similarity(shingle_by_id[record_id], opened_set)
                if is_near_duplicate(jaccard, containment, shorter, method):
                    opened_near.append({"record_exclusion_key": opened_key, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter})
            opened_near.sort(key=lambda item: (-item["jaccard"], -item["containment"], item["record_exclusion_key"]))
            cross_collision = len({by_id[member]["cohort"] for member in members}) > 1
            if exact_capture_hits or exact_text_hits or host_hits:
                routing = "EXCLUDED_OPENED_COHORT_EXACT_OR_HOST_OVERLAP"
            elif opened_near:
                routing = "MANUAL_OPENED_NEAR_DUPLICATE_REVIEW_REQUIRED"
            elif cross_collision and row["cohort"] == "EXTERNAL_HOLDOUT":
                routing = "EXCLUDED_HOLDOUT_CROSS_COHORT_COLLISION"
            elif cross_collision:
                routing = "DEVELOPMENT_CROSS_COHORT_COLLISION_REVIEW_REQUIRED"
            else:
                routing = "AUTOMATED_EXCLUSION_PASS_MANUAL_GROUP_REVIEW_REQUIRED"
        records.append({
            "record_id": record_id,
            "shortlist_id": row["shortlist_id"],
            "cohort": row["cohort"],
            "candidate_host": row["candidate_host"],
            "normalized_host_sha256": host_sha256(row["candidate_host"]),
            "raw_capture_sha256": row["raw_capture_sha256"],
            "text_sha256": row["text_sha256"],
            "minimum_content_passed": row["minimum_content_passed"],
            "opened_overlap": {"exact_capture_record_keys": exact_capture_hits, "exact_text_record_keys": exact_text_hits, "exact_normalized_host_record_keys": host_hits, "probable_near_duplicate_hits": opened_near},
            "candidate_internal_near_duplicate_hits": sorted(near_hits.get(record_id, []), key=lambda item: item["record_id"]),
            "technical_group": technical_group,
            "cross_cohort_group_collision": cross_collision,
            "routing_decision": routing,
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        })
    decisions = Counter(row["routing_decision"] for row in records)
    return {
        "analysis_id": "ISI_SEC_EDGAR_IAPD_POST_CAPTURE_EXCLUSION_GROUPING_V1",
        "created_at": release["created_at"],
        "status": "AUTOMATED_OFFLINE_ANALYSIS_COMPLETE_INDEPENDENT_QA_REQUIRED",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "release_qa": {"path": str(release_qa_path.resolve()), "sha256": sha256_file(release_qa_path)},
        "counts": {"manifest_rows": len(manifest), "minimum_content_pass_rows": len(passed), "opened_cohort_rows_compared": len(opened_texts), "routing_decisions": dict(sorted(decisions.items())), "internal_group_edges": len(edges), "transitive_groups": len({tuple(components[value]) for value in candidate_ids}), "cross_cohort_groups": len(cross_cohort_groups), "labels_created": 0},
        "cross_cohort_groups": [{"group_id": key, "members": value} for key, value in sorted(cross_cohort_groups.items())],
        "records": records,
        "gates": {"opened_exclusion_complete": True, "technical_grouping_complete": True, "development_holdout_collision_screen_complete": True, "manual_group_review_required": True, "human_label_review_allowed": False, "model_scoring_allowed": False, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "labels_created": 0, "model_operations": 0},
    }


def execute(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    output = Path(release["output"]["path"])
    if output.exists() or output.with_suffix(output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite grouping analysis")
    result = build(release_path, release_qa_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.release, args.release_qa)
    print(json.dumps({"analysis_id": result["analysis_id"], "status": result["status"], "counts": result["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
