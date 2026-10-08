"""Independently verify post-capture exclusions and transitive technical groups."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)*\b")
TOKEN = re.compile(r"[a-z0-9]+")
LEGAL = {"corp", "corporation", "inc", "incorporated", "limited", "llc", "llp", "lp", "ltd", "plc"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def entity_key(value: str) -> str:
    tokens = TOKEN.findall(unicodedata.normalize("NFKC", value).casefold())
    while tokens and tokens[-1] in LEGAL:
        tokens.pop()
    return " ".join(tokens)


def shingle_set(text: str, size: int) -> set[tuple[str, ...]]:
    value = unicodedata.normalize("NFKC", text).casefold()
    value = URL.sub(" urltoken ", value)
    value = EMAIL.sub(" emailtoken ", value)
    value = NUMBER.sub(" numbertoken ", value)
    tokens = TOKEN.findall(value)
    if not tokens:
        return set()
    if len(tokens) < size:
        return {tuple(tokens)}
    return {tuple(tokens[pos:pos + size]) for pos in range(len(tokens) - size + 1)}


def pair_score(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> tuple[float, float, int]:
    if not left or not right:
        return 0.0, 0.0, 0
    common = len(left.intersection(right))
    return common / len(left.union(right)), common / min(len(left), len(right)), min(len(left), len(right))


def flagged(metrics: tuple[float, float, int], method: dict[str, Any]) -> bool:
    jaccard, containment, shorter = metrics
    return jaccard >= float(method["jaccard_threshold"]) or (
        shorter >= int(method["minimum_shorter_shingles_for_containment_rule"])
        and containment >= float(method["containment_threshold"])
    )


def bfs_components(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    adjacent = {node: set() for node in nodes}
    for left, right in edges:
        adjacent[left].add(right)
        adjacent[right].add(left)
    result: dict[str, list[str]] = {}
    visited: set[str] = set()
    for start in sorted(nodes):
        if start in visited:
            continue
        queue = deque([start])
        component: list[str] = []
        visited.add(start)
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in sorted(adjacent[current]):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        members = sorted(component)
        for member in members:
            result[member] = members
    return result


def gid(prefix: str, members: list[str]) -> str:
    return f"{prefix}_{text_hash(chr(10).join(sorted(members)))[:16].upper()}"


def audit(config_path: Path, analysis_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    config = read_json(config_path)
    analysis = read_json(analysis_path)
    root = config_path.resolve().parents[1]
    paths: dict[str, Path] = {}
    for role, item in config["inputs"].items():
        path = resolve(root, item["path"])
        paths[role] = path
        if not path.is_file() or file_hash(path) != item["sha256"]:
            errors.append(f"Missing or changed input: {role}")
    if errors:
        return {"review_id": "ISI_TARGET_TEXT_CORPUS_V1_POST_CAPTURE_GROUPING_INDEPENDENT_QA_V1", "status": "FAIL", "errors": errors}

    queue_rows = read_jsonl(paths["candidate_queue"])
    candidates = {row["candidate_id"]: row for row in queue_rows}
    manifest = read_jsonl(paths["exact_text_manifest"])
    manifest_by_id = {row["candidate_id"]: row for row in manifest}
    passed_ids = sorted(row["candidate_id"] for row in manifest if row["minimum_content_passed"])
    index = read_json(paths["opened_external_exclusion_index"])
    opened_rows = {row["record_exclusion_key"]: row for row in index["records"]}
    opened_texts: dict[str, str] = {}
    for cohort in index["cohorts"]:
        path = resolve(root, cohort["artifact_path"])
        if file_hash(path) != cohort["artifact_sha256"]:
            errors.append(f"Opened cohort artifact changed: {cohort['cohort_id']}")
            continue
        for record in read_json(path)["records"]:
            record_id = record.get("case_id") or record.get("benchmark_record_id")
            key = f"{cohort['cohort_id']}::{record_id}"
            artifact = record["artifact"]
            text = artifact.get("text") if artifact.get("text") is not None else artifact.get("visible_text")
            opened_texts[key] = text
    if set(opened_texts) != set(opened_rows):
        errors.append("Opened text/index membership mismatch")
    for key, text in opened_texts.items():
        if text_hash(text) != opened_rows[key]["text_sha256"]:
            errors.append(f"Opened text hash mismatch: {key}")

    method = config["normalization_and_near_duplicate_method"]
    size = int(method["word_shingle_size"])
    candidate_texts: dict[str, str] = {}
    for candidate_id in passed_ids:
        row = manifest_by_id[candidate_id]
        data = Path(row["text_path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["text_sha256"]:
            errors.append(f"Candidate text changed: {candidate_id}")
        candidate_texts[candidate_id] = data.decode("utf-8")
    candidate_sets = {key: shingle_set(text, size) for key, text in candidate_texts.items()}
    opened_sets = {key: shingle_set(text, size) for key, text in opened_texts.items()}

    internal_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    near_edges: list[tuple[str, str]] = []
    for position, left in enumerate(passed_ids):
        for right in passed_ids[position + 1:]:
            metrics = pair_score(candidate_sets[left], candidate_sets[right])
            if flagged(metrics, method):
                jaccard, containment, shorter = metrics
                internal_hits[left].append({"candidate_id": right, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter})
                internal_hits[right].append({"candidate_id": left, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter})
                near_edges.append((left, right))
    opened_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate_id in passed_ids:
        for opened_key in sorted(opened_sets):
            metrics = pair_score(candidate_sets[candidate_id], opened_sets[opened_key])
            if flagged(metrics, method):
                jaccard, containment, shorter = metrics
                opened_hits[candidate_id].append({"record_exclusion_key": opened_key, "jaccard": round(jaccard, 6), "containment": round(containment, 6), "shorter_shingles": shorter})
        opened_hits[candidate_id].sort(key=lambda hit: (-hit["jaccard"], -hit["containment"], hit["record_exclusion_key"]))

    bucket_types: dict[str, dict[str, list[str]]] = {
        name: defaultdict(list) for name in ("case", "entity", "host", "text")
    }
    for candidate_id in passed_ids:
        candidate = candidates[candidate_id]
        reference, identity = candidate["reference"], candidate["candidate_identity"]
        bucket_types["case"][f"{reference['source_id']}::{reference['source_record_id']}"] .append(candidate_id)
        bucket_types["entity"][entity_key(identity["entity_name_from_reference"])].append(candidate_id)
        bucket_types["host"][identity["normalized_host_sha256"]].append(candidate_id)
        bucket_types["text"][manifest_by_id[candidate_id]["text_sha256"]].append(candidate_id)

    def edges_for(names: tuple[str, ...]) -> list[tuple[str, str]]:
        edges: list[tuple[str, str]] = []
        for name in names:
            for members in bucket_types[name].values():
                edges.extend((members[0], member) for member in members[1:])
        return edges

    case_edges = edges_for(("case",))
    entity_edges = edges_for(("entity", "host"))
    text_edges = edges_for(("text",))
    cases = bfs_components(passed_ids, case_edges)
    entities = bfs_components(passed_ids, entity_edges)
    near = bfs_components(passed_ids, text_edges + near_edges)
    transitive = bfs_components(passed_ids, case_edges + entity_edges + text_edges + near_edges)

    by_id = {row["candidate_id"]: row for row in analysis.get("records", [])}
    if set(by_id) != set(manifest_by_id):
        errors.append("Analysis/manifest candidate membership mismatch")
    capture_index: dict[str, list[str]] = defaultdict(list)
    text_index: dict[str, list[str]] = defaultdict(list)
    host_index: dict[str, list[str]] = defaultdict(list)
    for key, row in opened_rows.items():
        capture_index[row["capture_sha256"]].append(key)
        text_index[row["text_sha256"]].append(key)
        host_index[row["normalized_host_sha256"]].append(key)

    exact_match_records = 0
    for candidate_id, manifest_row in manifest_by_id.items():
        actual = by_id.get(candidate_id)
        if actual is None:
            continue
        if not manifest_row["minimum_content_passed"]:
            expected_decision = "NOT_REVIEWABLE_BELOW_MINIMUM"
            expected_groups = None
            expected_overlap = {"exact_capture_record_keys": [], "exact_text_record_keys": [], "exact_normalized_host_record_keys": [], "probable_near_duplicate_hits": []}
            expected_internal: list[dict[str, Any]] = []
        else:
            identity = candidates[candidate_id]["candidate_identity"]
            expected_overlap = {
                "exact_capture_record_keys": sorted(capture_index.get(manifest_row["raw_capture_sha256"], [])),
                "exact_text_record_keys": sorted(text_index.get(manifest_row["text_sha256"], [])),
                "exact_normalized_host_record_keys": sorted(host_index.get(identity["normalized_host_sha256"], [])),
                "probable_near_duplicate_hits": opened_hits[candidate_id],
            }
            if any(expected_overlap[key] for key in ("exact_capture_record_keys", "exact_text_record_keys", "exact_normalized_host_record_keys")):
                expected_decision = "EXCLUDED_OPENED_COHORT_EXACT_OR_HOST_OVERLAP"
            elif expected_overlap["probable_near_duplicate_hits"]:
                expected_decision = "MANUAL_OPENED_NEAR_DUPLICATE_REVIEW_REQUIRED"
            else:
                expected_decision = "AUTOMATED_EXCLUSION_PASS_MANUAL_GROUP_REVIEW_REQUIRED"
            expected_groups = {
                "group_semantics": "PROVISIONAL_EXCLUSION_CONTROL_ONLY",
                "case_or_campaign_group_id": gid("TTCCASE", cases[candidate_id]),
                "entity_or_host_family_group_id": gid("TTCENTITY", entities[candidate_id]),
                "near_duplicate_group_id": gid("TTCNDG", near[candidate_id]),
                "transitive_exclusion_group_id": gid("TTCX", transitive[candidate_id]),
                "transitive_group_members": transitive[candidate_id],
            }
            expected_internal = sorted(internal_hits[candidate_id], key=lambda hit: hit["candidate_id"])
        checks = (
            actual.get("opened_overlap") == expected_overlap,
            actual.get("candidate_internal_near_duplicate_hits") == expected_internal,
            actual.get("technical_groups") == expected_groups,
            actual.get("routing_decision") == expected_decision,
            actual.get("ground_truth_status") == "UNCERTAIN",
            actual.get("label_created") is False,
            actual.get("training_eligible") == "NO",
        )
        if all(checks):
            exact_match_records += 1
        else:
            errors.append(f"Independent record mismatch: {candidate_id}")

    gates = analysis.get("gates", {})
    if gates.get("human_label_review_allowed") is not False:
        errors.append("Human label review gate unexpectedly open")
    if gates.get("manual_cross_domain_case_clone_and_group_review_required") is not True:
        errors.append("Manual group-review requirement missing")
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_POST_CAPTURE_GROUPING_INDEPENDENT_QA_V1",
        "status": "PASS_INDEPENDENT_RECOMPUTATION" if not errors else "FAIL",
        "inputs": {
            "config": {"path": str(config_path), "sha256": file_hash(config_path)},
            "analysis": {"path": str(analysis_path), "sha256": file_hash(analysis_path)},
        },
        "checks": {
            "manifest_rows": len(manifest),
            "minimum_content_pass_rows": len(passed_ids),
            "opened_cohort_rows_recomputed": len(opened_rows),
            "record_level_exact_match_count": exact_match_records,
            "candidate_internal_near_duplicate_pairs": len(near_edges),
            "independent_transitive_group_count": len({gid("TTCX", transitive[item]) for item in passed_ids}),
            "labels_created": 0,
        },
        "decision": {
            "automated_post_capture_gate_passed": not errors,
            "manual_cross_domain_case_clone_and_group_review_allowed": not errors,
            "human_label_review_allowed": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
        "errors": errors,
        "safety_contract": config["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    result = audit(args.config, args.analysis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
