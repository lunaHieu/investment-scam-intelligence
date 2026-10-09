"""Reconcile frozen primary and blind second reviews without creating labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def reconcile(config_path: Path) -> dict[str, Any]:
    config = load(config_path)
    root = config_path.resolve().parents[1]
    paths: dict[str, Path] = {}
    for role, item in config["inputs"].items():
        path = resolve(root, item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError(f"Missing or changed input: {role}")
        paths[role] = path
    primary = {row["candidate_id"]: row for row in load(paths["primary_review"])["records"]}
    second = {row["blind_id"]: row for row in load(paths["blind_second_review"])["records"]}
    mapping = load(paths["private_mapping"])["records"]
    packet = {row["blind_id"]: row for row in load(paths["blind_packet"])["records"]}
    if len(mapping) != config["expected_population"]:
        raise ValueError("Mapping population changed")

    registration_keys: dict[tuple[str, str], list[str]] = defaultdict(list)
    for blind_id, row in packet.items():
        registration = row["official_evidence"].get("registration_reference")
        if registration:
            key = (str(registration["sec_number"]), str(registration["source_record_id"]))
            registration_keys[key].append(blind_id)
    collisions = {"|".join(key): ids for key, ids in registration_keys.items() if len(ids) > 1}
    if collisions:
        raise ValueError(f"Registration-key collisions remain: {collisions}")

    rows = []
    disagreements = []
    for link in sorted(mapping, key=lambda item: item["candidate_id"]):
        candidate_id = link["candidate_id"]
        blind_id = link["blind_id"]
        first = primary[candidate_id]["primary_recommendation"]
        second_value = second[blind_id]["second_recommendation"]
        if first == second_value:
            recommendation = first
            disposition = "AGREEMENT_CARRIED_FORWARD_AS_NONLABEL_RECOMMENDATION"
            rationale = "Both frozen reviews independently reached the same recommendation; the agreement is retained for owner review but does not create a label or training eligibility."
        else:
            disagreements.append(candidate_id)
            resolution = config["disagreement_resolutions"][candidate_id]
            recommendation = resolution["reconciled_recommendation"]
            disposition = resolution["disposition"]
            rationale = resolution["rationale"]
        rows.append({
            "candidate_id": candidate_id,
            "blind_id": blind_id,
            "primary_recommendation": first,
            "second_recommendation": second_value,
            "reconciled_recommendation": recommendation,
            "disposition": disposition,
            "rationale": rationale,
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        })
    if sorted(disagreements) != sorted(config["expected_disagreements"]):
        raise ValueError(f"Unexpected disagreement set: {disagreements}")
    counts = Counter(row["reconciled_recommendation"] for row in rows)
    return {
        "reconciliation_id": config["reconciliation_id"],
        "status": "RECONCILIATION_COMPLETE_OWNER_ACCEPTANCE_REQUIRED",
        "config": {"path": str(config_path), "sha256": sha(config_path)},
        "registration_identity_audit": {"registration_records": len(registration_keys), "duplicate_composite_keys": 0, "collisions": {}},
        "records": rows,
        "summary": {
            "reviewed_records": len(rows),
            "agreements": len(rows) - len(disagreements),
            "disagreements": len(disagreements),
            "reconciled_recommendation_counts": dict(sorted(counts.items())),
            "labels_created": 0,
            "training_eligible_records": 0,
        },
        "decision": {"reconciliation_complete": True, "owner_acceptance_required": True, "ground_truth_labeling_completed": False, "training_allowed": False},
        "safety_contract": config["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load(args.config)
    output = Path(config["outputs"]["reconciliation"])
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    result = reconcile(args.config)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"summary": result["summary"], "registration_identity_audit": result["registration_identity_audit"], "output": str(output), "sha256": sha(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
