"""Build label-free post-capture exclusions and technical groups offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract_target_text_corpus_v1_exact_text import load_json, load_jsonl, sha256_file


URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")
TOKEN_RE = re.compile(r"[a-z0-9]+")
LEGAL_SUFFIXES = {"corp", "corporation", "inc", "incorporated", "limited", "llc", "llp", "lp", "ltd", "plc"}


class UnionFind:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        first, second = self.find(left), self.find(right)
        if first != second:
            self.parent[max(first, second)] = min(first, second)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def verify_input(root: Path, item: dict[str, Any], role: str) -> Path:
    path = resolve(root, item.get("path", ""))
    if not path.is_file() or sha256_file(path) != item.get("sha256"):
        raise ValueError(f"Missing or changed input: {role}")
    return path


def normalize_entity(value: str) -> str:
    tokens = TOKEN_RE.findall(unicodedata.normalize("NFKC", value).casefold())
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalized_tokens(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold()
    value = URL_RE.sub(" urltoken ", value)
    value = EMAIL_RE.sub(" emailtoken ", value)
    value = NUMBER_RE.sub(" numbertoken ", value)
    return TOKEN_RE.findall(value)


def shingles(text: str, size: int = 5) -> set[tuple[str, ...]]:
    tokens = normalized_tokens(text)
    if not tokens:
        return set()
    if len(tokens) < size:
        return {tuple(tokens)}
    return {tuple(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}


def similarity(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> tuple[float, float, int]:
    if not left or not right:
        return 0.0, 0.0, 0
    intersection = len(left & right)
    return intersection / len(left | right), intersection / min(len(left), len(right)), min(len(left), len(right))


def is_near_duplicate(jaccard: float, containment: float, shorter: int, method: dict[str, Any]) -> bool:
    return jaccard >= float(method["jaccard_threshold"]) or (
        shorter >= int(method["minimum_shorter_shingles_for_containment_rule"])
        and containment >= float(method["containment_threshold"])
    )


def component_map(values: list[str], edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    union_find = UnionFind(values)
    for left, right in edges:
        union_find.union(left, right)
    grouped: dict[str, list[str]] = defaultdict(list)
    for value in values:
        grouped[union_find.find(value)].append(value)
    return {member: sorted(grouped[union_find.find(member)]) for member in values}


def group_id(prefix: str, members: list[str]) -> str:
    digest = sha256_text("\n".join(sorted(members)))[:16].upper()
    return f"{prefix}_{digest}"


def load_opened_texts(index: dict[str, Any], root: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for cohort in index["cohorts"]:
        artifact_path = resolve(root, cohort["artifact_path"])
        if sha256_file(artifact_path) != cohort["artifact_sha256"]:
            raise ValueError(f"Opened cohort artifact changed: {artifact_path}")
        artifact_data = load_json(artifact_path)
        if len(artifact_data.get("records", [])) != cohort["record_count"]:
            raise ValueError(f"Opened cohort count changed: {cohort['cohort_id']}")
        for record in artifact_data["records"]:
            record_id = record.get("case_id") or record.get("benchmark_record_id")
            key = f"{cohort['cohort_id']}::{record_id}"
            artifact = record.get("artifact", {})
            text = artifact.get("text") if artifact.get("text") is not None else artifact.get("visible_text")
            if not isinstance(text, str):
                raise ValueError(f"Opened cohort text missing: {key}")
            texts[key] = text
    return texts


def build(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    if config.get("status") != "FROZEN_BEFORE_POST_CAPTURE_ANALYSIS":
        raise ValueError("Post-capture protocol is not frozen")
    root = config_path.resolve().parents[1]
    paths = {
        role: verify_input(root, config["inputs"].get(role, {}), role)
        for role in (
            "exact_text_result_registry", "candidate_queue", "exact_text_manifest",
            "opened_external_exclusion_index", "legacy_group_remediation_map",
        )
    }
    result_registry = load_json(paths["exact_text_result_registry"])
    if result_registry.get("decision", {}).get("post_capture_exclusion_and_grouping_allowed") is not True:
        raise ValueError("Exact-text result has not released post-capture analysis")
    if result_registry.get("decision", {}).get("human_label_review_allowed") is not False:
        raise ValueError("Human label review gate unexpectedly open")
    exclusion_index = load_json(paths["opened_external_exclusion_index"])
    remediation = load_json(paths["legacy_group_remediation_map"])
    expected = config["expected_input"]
    if exclusion_index.get("counts", {}).get("opened_records") != expected["opened_cohort_rows"]:
        raise ValueError("Opened exclusion population changed")
    if remediation.get("counts", {}).get("legacy_records") != expected["legacy_remediation_rows"]:
        raise ValueError("Legacy remediation population changed")

    candidates = {row["candidate_id"]: row for row in load_jsonl(paths["candidate_queue"])}
    manifest = load_jsonl(paths["exact_text_manifest"])
    if len(manifest) != expected["manifest_rows"]:
        raise ValueError("Exact-text manifest population changed")
    passed = [row for row in manifest if row["minimum_content_passed"]]
    if len(passed) != expected["minimum_content_pass_rows"]:
        raise ValueError("Minimum-content population changed")
    if len({row["candidate_id"] for row in manifest}) != len(manifest):
        raise ValueError("Duplicate manifest candidate ID")

    opened_by_key = {row["record_exclusion_key"]: row for row in exclusion_index["records"]}
    opened_texts = load_opened_texts(exclusion_index, root)
    if set(opened_texts) != set(opened_by_key):
        raise ValueError("Opened cohort text/index membership mismatch")
    for key, text in opened_texts.items():
        if sha256_text(text) != opened_by_key[key]["text_sha256"]:
            raise ValueError(f"Opened cohort text hash mismatch: {key}")

    opened_capture = defaultdict(list)
    opened_text_hash = defaultdict(list)
    opened_host = defaultdict(list)
    for key, row in opened_by_key.items():
        opened_capture[row["capture_sha256"]].append(key)
        opened_text_hash[row["text_sha256"]].append(key)
        opened_host[row["normalized_host_sha256"]].append(key)
    method = config["normalization_and_near_duplicate_method"]
    opened_shingles = {key: shingles(text, int(method["word_shingle_size"])) for key, text in opened_texts.items()}

    candidate_texts: dict[str, str] = {}
    candidate_shingles: dict[str, set[tuple[str, ...]]] = {}
    for row in passed:
        path = Path(row["text_path"])
        text_bytes = path.read_bytes()
        if hashlib.sha256(text_bytes).hexdigest() != row["text_sha256"]:
            raise ValueError(f"Candidate text hash mismatch: {row['candidate_id']}")
        text = text_bytes.decode("utf-8")
        candidate_texts[row["candidate_id"]] = text
        candidate_shingles[row["candidate_id"]] = shingles(text, int(method["word_shingle_size"]))

    candidate_ids = sorted(candidate_texts)
    internal_near: dict[str, list[dict[str, Any]]] = defaultdict(list)
    near_edges: list[tuple[str, str]] = []
    for index, left in enumerate(candidate_ids):
        for right in candidate_ids[index + 1:]:
            jaccard, containment, shorter = similarity(candidate_shingles[left], candidate_shingles[right])
            if is_near_duplicate(jaccard, containment, shorter, method):
                hit_left = {"candidate_id": right, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter}
                hit_right = {"candidate_id": left, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter}
                internal_near[left].append(hit_left)
                internal_near[right].append(hit_right)
                near_edges.append((left, right))

    opened_near: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate_id in candidate_ids:
        for opened_key, opened_set in opened_shingles.items():
            jaccard, containment, shorter = similarity(candidate_shingles[candidate_id], opened_set)
            if is_near_duplicate(jaccard, containment, shorter, method):
                opened_near[candidate_id].append({
                    "record_exclusion_key": opened_key,
                    "jaccard": round(jaccard, 6),
                    "containment": round(containment, 6),
                    "shorter_shingles": shorter,
                })
        opened_near[candidate_id].sort(key=lambda hit: (-hit["jaccard"], -hit["containment"], hit["record_exclusion_key"]))

    case_edges: list[tuple[str, str]] = []
    entity_edges: list[tuple[str, str]] = []
    exact_text_edges: list[tuple[str, str]] = []
    buckets: dict[str, dict[str, list[str]]] = {
        "case": defaultdict(list), "entity": defaultdict(list), "host": defaultdict(list), "text": defaultdict(list)
    }
    manifest_by_id = {row["candidate_id"]: row for row in manifest}
    for candidate_id in candidate_ids:
        candidate = candidates[candidate_id]
        row = manifest_by_id[candidate_id]
        reference = candidate["reference"]
        identity = candidate["candidate_identity"]
        buckets["case"][f"{reference['source_id']}::{reference['source_record_id']}"] .append(candidate_id)
        buckets["entity"][normalize_entity(identity["entity_name_from_reference"])].append(candidate_id)
        buckets["host"][identity["normalized_host_sha256"]].append(candidate_id)
        buckets["text"][row["text_sha256"]].append(candidate_id)
    for members in buckets["case"].values():
        case_edges.extend((members[0], member) for member in members[1:])
    for kind in ("entity", "host"):
        for members in buckets[kind].values():
            entity_edges.extend((members[0], member) for member in members[1:])
    for members in buckets["text"].values():
        exact_text_edges.extend((members[0], member) for member in members[1:])
    case_components = component_map(candidate_ids, case_edges)
    entity_components = component_map(candidate_ids, entity_edges)
    near_components = component_map(candidate_ids, exact_text_edges + near_edges)
    transitive_components = component_map(candidate_ids, case_edges + entity_edges + exact_text_edges + near_edges)

    records: list[dict[str, Any]] = []
    for manifest_row in sorted(manifest, key=lambda row: row["candidate_id"]):
        candidate_id = manifest_row["candidate_id"]
        candidate = candidates[candidate_id]
        identity = candidate["candidate_identity"]
        if not manifest_row["minimum_content_passed"]:
            decision = "NOT_REVIEWABLE_BELOW_MINIMUM"
            exact_capture_hits: list[str] = []
            exact_text_hits: list[str] = []
            host_hits: list[str] = []
            near_hits: list[dict[str, Any]] = []
            groups = None
        else:
            exact_capture_hits = sorted(opened_capture.get(manifest_row["raw_capture_sha256"], []))
            exact_text_hits = sorted(opened_text_hash.get(manifest_row["text_sha256"], []))
            host_hits = sorted(opened_host.get(identity["normalized_host_sha256"], []))
            near_hits = opened_near[candidate_id]
            if exact_capture_hits or exact_text_hits or host_hits:
                decision = "EXCLUDED_OPENED_COHORT_EXACT_OR_HOST_OVERLAP"
            elif near_hits:
                decision = "MANUAL_OPENED_NEAR_DUPLICATE_REVIEW_REQUIRED"
            else:
                decision = "AUTOMATED_EXCLUSION_PASS_MANUAL_GROUP_REVIEW_REQUIRED"
            groups = {
                "group_semantics": "PROVISIONAL_EXCLUSION_CONTROL_ONLY",
                "case_or_campaign_group_id": group_id("TTCCASE", case_components[candidate_id]),
                "entity_or_host_family_group_id": group_id("TTCENTITY", entity_components[candidate_id]),
                "near_duplicate_group_id": group_id("TTCNDG", near_components[candidate_id]),
                "transitive_exclusion_group_id": group_id("TTCX", transitive_components[candidate_id]),
                "transitive_group_members": transitive_components[candidate_id],
            }
        records.append({
            "candidate_id": candidate_id,
            "channel_id": manifest_row["channel_id"],
            "channel_target_stratum": manifest_row["channel_target_stratum"],
            "candidate_host": manifest_row["candidate_host"],
            "normalized_entity_name": normalize_entity(identity["entity_name_from_reference"]),
            "normalized_host_sha256": identity["normalized_host_sha256"],
            "raw_capture_sha256": manifest_row["raw_capture_sha256"],
            "text_sha256": manifest_row["text_sha256"],
            "minimum_content_passed": manifest_row["minimum_content_passed"],
            "opened_overlap": {
                "exact_capture_record_keys": exact_capture_hits,
                "exact_text_record_keys": exact_text_hits,
                "exact_normalized_host_record_keys": host_hits,
                "probable_near_duplicate_hits": near_hits,
            },
            "candidate_internal_near_duplicate_hits": sorted(internal_near.get(candidate_id, []), key=lambda hit: hit["candidate_id"]),
            "technical_groups": groups,
            "routing_decision": decision,
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        })

    decisions = Counter(row["routing_decision"] for row in records)
    reviewable_records = [row for row in records if row["minimum_content_passed"]]
    transitive_groups = {
        row["technical_groups"]["transitive_exclusion_group_id"]
        for row in reviewable_records
    }
    cross_stratum_groups = []
    for group in sorted(transitive_groups):
        members = [row for row in reviewable_records if row["technical_groups"]["transitive_exclusion_group_id"] == group]
        strata = sorted({row["channel_target_stratum"] for row in members})
        if len(strata) > 1:
            cross_stratum_groups.append({"group_id": group, "members": [row["candidate_id"] for row in members], "target_strata": strata})
    return {
        "analysis_id": "ISI_TARGET_TEXT_CORPUS_V1_POST_CAPTURE_EXCLUSION_GROUPING_V1",
        "created_at": "2026-10-08",
        "status": "AUTOMATED_OFFLINE_ANALYSIS_COMPLETE_MANUAL_GROUP_REVIEW_REQUIRED",
        "config": {"path": str(config_path), "sha256": sha256_file(config_path)},
        "counts": {
            "manifest_rows": len(records),
            "minimum_content_pass_rows": len(reviewable_records),
            "opened_cohort_rows_compared": len(opened_texts),
            "routing_decisions": dict(sorted(decisions.items())),
            "candidate_internal_near_duplicate_pairs": len(near_edges),
            "transitive_exclusion_groups": len(transitive_groups),
            "cross_target_stratum_transitive_groups": len(cross_stratum_groups),
            "labels_created": 0,
        },
        "cross_target_stratum_groups": cross_stratum_groups,
        "records": records,
        "gates": {
            "exact_and_host_overlap_checks_complete": True,
            "normalized_near_duplicate_screen_complete": True,
            "technical_grouping_complete": True,
            "manual_cross_domain_case_clone_and_group_review_required": True,
            "human_label_review_allowed": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": config["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_json(args.config)
    output = Path(config["outputs"]["analysis"])
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    result = build(args.config)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"analysis_id": result["analysis_id"], "status": result["status"], "counts": result["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
