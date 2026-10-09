"""Build a blind second-review packet and a separately stored private ID map."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def opaque_id(namespace: str, candidate_id: str) -> str:
    digest = hashlib.sha256(f"{namespace}\0{candidate_id}".encode("utf-8")).hexdigest()[:20]
    return f"TTCV1_BLIND_{digest.upper()}"


def build(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = load(config_path)
    if config.get("status") != "FROZEN_BEFORE_BLIND_SECOND_REVIEW":
        raise ValueError("Blind second-review protocol is not frozen")
    root = config_path.resolve().parents[1]
    paths: dict[str, Path] = {}
    for role, item in config["inputs"].items():
        path = resolve(root, item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError(f"Missing or changed input: {role}")
        paths[role] = path
    gate = load(paths["primary_result_registry_gate"])
    if gate.get("decision", {}).get("blind_independent_second_review_allowed") is not True:
        raise ValueError("Blind second review has not been released")
    if gate.get("decision", {}).get("ground_truth_labeling_completed") is not False:
        raise ValueError("Ground-truth gate unexpectedly open")
    source = load(paths["unreviewed_primary_packet"])
    if source.get("status") != "FROZEN_UNREVIEWED_PACKET":
        raise ValueError("Expected the original unreviewed evidence packet")
    namespace = config["blinding"]["opaque_id_namespace"]
    records = []
    mapping = []
    for row in sorted(source["records"], key=lambda item: item["candidate_id"]):
        blind_id = opaque_id(namespace, row["candidate_id"])
        mapping.append({"blind_id": blind_id, "candidate_id": row["candidate_id"]})
        records.append({
            "blind_id": blind_id,
            "candidate_identity": row["candidate_identity"],
            "capture": {
                "archive_url": row["capture"]["archive_url"],
                "snapshot_timestamp": row["capture"]["snapshot_timestamp"],
                "text_sha256": row["capture"]["text_sha256"],
                "visible_text_characters": row["capture"]["visible_text_characters"],
                "text": row["capture"]["text"],
            },
            "official_evidence": row["official_evidence"],
            "review_form": {
                "second_recommendation": "PENDING_BLIND_SECOND_REVIEW",
                "identity_linkage": "PENDING",
                "task_relevance": "PENDING",
                "capture_chronology": "PENDING",
                "repurpose_or_parking": "PENDING",
                "contradiction_screen": "PENDING",
                "supporting_facts": [],
                "uncertainty_reasons": [],
                "rationale": None,
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            },
        })
    if len(records) != config["expected_review_population"] or len({row["blind_id"] for row in records}) != len(records):
        raise ValueError("Blind population is incomplete or IDs collided")
    packet = {
        "packet_id": "ISI_TARGET_TEXT_CORPUS_V1_BLIND_SECOND_REVIEW_PACKET_V1",
        "status": "FROZEN_BLIND_UNREVIEWED_PACKET",
        "config": {"path": str(config_path), "sha256": sha(config_path)},
        "review_scope": config["review_scope"],
        "blinding_contract": config["blinding"],
        "record_count": len(records),
        "records": records,
        "safety_contract": config["safety_contract"],
    }
    private_mapping = {
        "mapping_id": "ISI_TARGET_TEXT_CORPUS_V1_BLIND_SECOND_REVIEW_PRIVATE_MAPPING_V1",
        "status": "PRIVATE_DO_NOT_EXPOSE_TO_SECOND_REVIEWER",
        "blind_packet_sha256_pending_until_write": True,
        "record_count": len(mapping),
        "records": mapping,
    }
    return packet, private_mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load(args.config)
    packet_path = Path(config["outputs"]["blind_packet"])
    mapping_path = Path(config["outputs"]["private_mapping"])
    if packet_path.exists() or mapping_path.exists():
        raise FileExistsError("Refusing to overwrite blind packet or private mapping")
    packet, mapping = build(args.config)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    with packet_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(packet, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    mapping["blind_packet_sha256_pending_until_write"] = False
    mapping["blind_packet"] = {"path": str(packet_path), "sha256": sha(packet_path)}
    with mapping_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(mapping, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({
        "packet": {"path": str(packet_path), "sha256": sha(packet_path)},
        "private_mapping": {"path": str(mapping_path), "sha256": sha(mapping_path)},
        "record_count": packet["record_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
