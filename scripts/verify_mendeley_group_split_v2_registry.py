"""Verify the frozen Mendeley group_split_v2 registry and local artifacts.

The verifier reconstructs text components directly from the raw/output rows; it
does not accept the builder report as proof of preservation or leakage control.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from audit_mendeley_text_overlap import (
    normalize_near_template_v2,
    normalize_surface,
    normalize_template,
    normalize_template_v2,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RAW_SHA256 = "a4b336074176efb5746d1981506c1f1faba19a1b0a20f3b9e95dc8be94ea2504"
EXPECTED_SPLIT_SHA256 = "98f75387a4a598d85a6f721d10808979bda694dad8f85354d595679bdd96e734"
EXPECTED_PARTITION_COUNTS = {
    "train": 3916,
    "validation": 838,
    "test": 838,
    "auxiliary": 10607,
    "quarantine": 3,
}
EXPECTED_CONFLICT_IDS = {"phishing_5164", "phishing_5168", "phishing_14168"}
EXPECTED_DERIVED_FIELDS = [
    "original_partition",
    "split_group_id",
    "benchmark_eligible",
    "split_exclusion_reason",
    "entity_group_id",
    "entity_post_index",
]
AUXILIARY_REASON = "entity_template_graph_not_splittable_without_leakage"
QUARANTINE_REASON = "conflicting_labels_within_duplicate_template_group"
BENCHMARK_PARTITIONS = {"train", "validation", "test"}
FAKE_RE = re.compile(
    r"^fake_profile_post_(?P<account>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12})_"
    r"(?P<post_index>[0-9]+)$"
)
GROUPING_RULES = (
    ("surface_normalized", normalize_surface, 1),
    ("legacy_template", normalize_template, 10),
    ("near_template_v2", normalize_near_template_v2, 1),
    ("template_v2", normalize_template_v2, 10),
)


class DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def key_eligible(key: str, minimum_tokens: int) -> bool:
    return bool(key) and len(key.split()) >= minimum_tokens


def reconstruct_components(rows: list[dict[str, str]]) -> list[list[int]]:
    dsu = DisjointSet(len(rows))
    for _, normalizer, minimum_tokens in GROUPING_RULES:
        first: dict[str, int] = {}
        for index, row in enumerate(rows):
            key = normalizer(row.get("text_content") or "")
            if not key_eligible(key, minimum_tokens):
                continue
            previous = first.get(key)
            if previous is None:
                first[key] = index
            else:
                dsu.union(previous, index)
    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        grouped[dsu.find(index)].append(index)
    return list(grouped.values())


def expected_group_id(rows: list[dict[str, str]], indices: list[int]) -> str:
    membership = "\n".join(sorted(rows[index]["record_id"] for index in indices))
    return "GRP2_" + sha256_text(membership)[:16].upper()


def verify_raw_preservation(
    raw_fields: list[str],
    raw_rows: list[dict[str, str]],
    split_fields: list[str],
    split_rows: list[dict[str, str]],
) -> None:
    if split_fields != raw_fields + EXPECTED_DERIVED_FIELDS:
        raise ValueError("Derived CSV schema/order does not equal raw fields plus V2 provenance")
    if len(raw_rows) != 16_202 or len(split_rows) != len(raw_rows):
        raise ValueError("Raw/derived row count mismatch")
    raw_ids = [row["record_id"] for row in raw_rows]
    split_ids = [row["record_id"] for row in split_rows]
    if raw_ids != split_ids or len(set(raw_ids)) != len(raw_ids):
        raise ValueError("Raw record IDs/order are not preserved exactly")
    for raw, split in zip(raw_rows, split_rows):
        for field in raw_fields:
            if field == "partition":
                if split["original_partition"] != raw[field]:
                    raise ValueError(f"original_partition mismatch for {raw['record_id']}")
            elif split[field] != raw[field]:
                raise ValueError(f"Raw field {field} changed for {raw['record_id']}")
        if split["label"] != raw["label"]:
            raise ValueError(f"Source label changed for {raw['record_id']}")


def verify_components(rows: list[dict[str, str]]) -> dict:
    components = reconstruct_components(rows)
    group_ids = set()
    benchmark_components = 0
    conflicting_components = []
    for indices in components:
        expected_id = expected_group_id(rows, indices)
        actual_ids = {rows[index]["split_group_id"] for index in indices}
        partitions = {rows[index]["partition"] for index in indices}
        sources = {rows[index]["source_dataset"] for index in indices}
        labels = {rows[index]["label"] for index in indices}
        if actual_ids != {expected_id}:
            raise ValueError(f"Unstable or incorrect split_group_id for {expected_id}")
        if expected_id in group_ids:
            raise ValueError(f"split_group_id collision: {expected_id}")
        group_ids.add(expected_id)
        if len(partitions) != 1 or len(sources) != 1:
            raise ValueError(f"Component crosses partition/source: {expected_id}")
        partition = next(iter(partitions))
        source = next(iter(sources))
        if source == "fake_profile_post":
            if partition != "auxiliary":
                raise ValueError(f"Fake-profile component escaped auxiliary: {expected_id}")
        elif len(labels) > 1:
            conflicting_components.append(indices)
            if partition != "quarantine":
                raise ValueError(f"Mixed-label component escaped quarantine: {expected_id}")
        else:
            benchmark_components += 1
            if partition not in BENCHMARK_PARTITIONS:
                raise ValueError(f"Eligible component excluded from benchmark: {expected_id}")
    conflict_ids = {
        rows[index]["record_id"]
        for indices in conflicting_components
        for index in indices
    }
    if conflict_ids != EXPECTED_CONFLICT_IDS or len(conflicting_components) != 1:
        raise ValueError("Reconstructed mixed-label component does not match quarantine")
    return {
        "text_component_count": len(components),
        "benchmark_component_count": benchmark_components,
        "largest_component_rows": max(map(len, components)),
        "largest_benchmark_component_rows": max(
            len(indices)
            for indices in components
            if rows[indices[0]]["partition"] in BENCHMARK_PARTITIONS
        ),
    }


def verify_entity_routing(rows: list[dict[str, str]]) -> dict:
    entities: dict[str, list[dict[str, str]]] = defaultdict(list)
    entity_indices = set()
    for row in rows:
        is_fake = row["source_dataset"] == "fake_profile_post"
        if not is_fake:
            if row["entity_group_id"] or row["entity_post_index"]:
                raise ValueError(f"Non-fake row has entity provenance: {row['record_id']}")
            continue
        match = FAKE_RE.fullmatch(row["record_id"])
        if not match:
            raise ValueError(f"Malformed fake-profile record_id: {row['record_id']}")
        account = str(uuid.UUID(match.group("account"))).lower()
        post_index = int(match.group("post_index"))
        if row["entity_group_id"] != account or row["entity_post_index"] != str(post_index):
            raise ValueError(f"Entity provenance mismatch: {row['record_id']}")
        key = (account, post_index)
        if key in entity_indices:
            raise ValueError(f"Duplicate entity/post index: {key}")
        entity_indices.add(key)
        entities[account].append(row)
        if (
            row["partition"] != "auxiliary"
            or row["benchmark_eligible"] != "0"
            or row["split_exclusion_reason"] != AUXILIARY_REASON
        ):
            raise ValueError(f"Invalid fake-profile routing: {row['record_id']}")
    if len(entities) != 1_387 or len(entity_indices) != 10_607:
        raise ValueError("Fake-profile entity count mismatch")
    if any(len({row["partition"] for row in values}) != 1 for values in entities.values()):
        raise ValueError("Fake-profile entity crosses partitions")
    return {"entity_count": len(entities), "entity_post_pair_count": len(entity_indices)}


def verify_routing_fields(rows: list[dict[str, str]]) -> None:
    quarantine_ids = set()
    for row in rows:
        partition = row["partition"]
        if partition in BENCHMARK_PARTITIONS:
            expected = ("1", "")
        elif partition == "auxiliary":
            expected = ("0", AUXILIARY_REASON)
        elif partition == "quarantine":
            expected = ("0", QUARANTINE_REASON)
            quarantine_ids.add(row["record_id"])
        else:
            raise ValueError(f"Unknown derived partition: {partition}")
        actual = (row["benchmark_eligible"], row["split_exclusion_reason"])
        if actual != expected:
            raise ValueError(f"Routing fields mismatch for {row['record_id']}")
    if quarantine_ids != EXPECTED_CONFLICT_IDS:
        raise ValueError("Quarantine record IDs mismatch")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "registry" / "splits" / "mendeley_group_split_v2.json",
    )
    args = parser.parse_args()
    registry = load_json(args.registry)
    if registry["split_id"] != "MENDELEY_GROUP_SPLIT_V2":
        raise ValueError("Unexpected split_id")
    if registry["status"] != "FROZEN_DERIVED_SPLIT":
        raise ValueError("Split registry is not frozen")

    artifacts = {item["role"]: item for item in registry["artifacts"]}
    expected_roles = {"raw_csv", "derived_split_csv", "split_report", "split_audit"}
    if set(artifacts) != expected_roles:
        raise ValueError("Split registry artifact roles mismatch")
    paths = {}
    for role, artifact in artifacts.items():
        path = Path(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_hash = sha256_file(path)
        if actual_hash != artifact["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {role}: {actual_hash}")
        paths[role] = path
    if artifacts["raw_csv"]["sha256"] != EXPECTED_RAW_SHA256:
        raise ValueError("Raw hash does not match pinned Mendeley V2 manifest")
    if artifacts["derived_split_csv"]["sha256"] != EXPECTED_SPLIT_SHA256:
        raise ValueError("Derived split hash does not match frozen V2")

    raw_fields, raw_rows = read_csv(paths["raw_csv"])
    split_fields, split_rows = read_csv(paths["derived_split_csv"])
    verify_raw_preservation(raw_fields, raw_rows, split_fields, split_rows)
    verify_routing_fields(split_rows)
    partition_counts = Counter(row["partition"] for row in split_rows)
    if dict(partition_counts) != EXPECTED_PARTITION_COUNTS:
        raise ValueError(f"Partition count mismatch: {dict(partition_counts)}")
    component_profile = verify_components(split_rows)
    if component_profile != {
        "text_component_count": 5762,
        "benchmark_component_count": 5399,
        "largest_component_rows": 398,
        "largest_benchmark_component_rows": 12,
    }:
        raise ValueError(f"Component profile mismatch: {component_profile}")
    entity_profile = verify_entity_routing(split_rows)

    report = load_json(paths["split_report"])
    if report["status"] != "FROZEN_DERIVED_SPLIT":
        raise ValueError("Builder report status mismatch")
    if report["output"]["sha256"] != EXPECTED_SPLIT_SHA256:
        raise ValueError("Builder report output hash mismatch")
    if not all(report["quality_gates"].values()):
        raise ValueError("Builder report contains a failed quality gate")
    if report["quality"]["row_count_by_partition"] != registry["routing_contract"]["partition_counts"]:
        raise ValueError("Report/registry routing counts mismatch")

    audit = load_json(paths["split_audit"])
    if audit["status"] != "FROZEN_DIAGNOSTIC_AUDIT":
        raise ValueError("Audit status mismatch")
    if audit["input"]["sha256"] != EXPECTED_SPLIT_SHA256:
        raise ValueError("Audit input hash mismatch")
    if not all(audit["structural_quality_gates"].values()):
        raise ValueError("Audit contains a failed structural gate")
    if audit["scope"]["classifier_trained"] is not False:
        raise ValueError("Split audit must not train a classifier")
    for partition in ("validation", "test"):
        actual = audit["nearest_train_similarity"][partition]["overall"]
        expected = registry["residual_similarity_diagnostic"][partition]
        if actual != expected:
            raise ValueError(f"Residual similarity mismatch for {partition}")

    safety = registry["safety_contract"]
    if (
        safety["raw_files_modified"] is not False
        or safety["network_operations"] != 0
        or safety["source_labels_changed"] != 0
        or safety["model_training_performed"] is not False
        or safety["model_artifacts_created"] != []
    ):
        raise ValueError("Registry safety contract is invalid")
    if registry["usage_policy"]["external_or_gold_test"] is not False:
        raise ValueError("V2 must not be described as external or Gold")

    print(
        "Mendeley group_split_v2 registry valid: 16,202 raw rows preserved; "
        "3,916/838/838 benchmark, 10,607 auxiliary, 3 quarantine; "
        f"{component_profile['text_component_count']} components and "
        f"{entity_profile['entity_count']} fake-profile entities independently checked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
