"""Build the frozen evidence packet for bounded manual group review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d() .-]{6,}\d)(?!\w)")


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def build(config_path: Path) -> dict[str, Any]:
    config = load(config_path)
    if config.get("status") != "FROZEN_BEFORE_MANUAL_GROUP_REVIEW":
        raise ValueError("Manual group-review protocol is not frozen")
    root = config_path.resolve().parents[1]
    paths = {}
    for role, item in config["inputs"].items():
        path = resolve(root, item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError(f"Missing or changed input: {role}")
        paths[role] = path
    registry = load(paths["post_capture_result_registry"])
    if registry.get("decision", {}).get("manual_cross_domain_case_clone_and_group_review_allowed") is not True:
        raise ValueError("Manual group review has not been released")
    if registry.get("decision", {}).get("human_label_review_allowed") is not False:
        raise ValueError("Label-review gate unexpectedly open")
    analysis = load(paths["post_capture_analysis"])
    queue = {row["candidate_id"]: row for row in load_jsonl(paths["candidate_queue"])}
    manifest = {row["candidate_id"]: row for row in load_jsonl(paths["exact_text_manifest"])}
    population = [row for row in analysis["records"] if row["minimum_content_passed"]]
    if len(population) != config["expected_review_population"]:
        raise ValueError("Manual review population changed")
    rows = []
    for grouped in sorted(population, key=lambda row: row["candidate_id"]):
        candidate_id = grouped["candidate_id"]
        candidate = queue[candidate_id]
        text_row = manifest[candidate_id]
        text_path = Path(text_row["text_path"])
        text = text_path.read_text(encoding="utf-8")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != text_row["text_sha256"]:
            raise ValueError(f"Text changed: {candidate_id}")
        emails = sorted({value.rstrip(".,;:)").casefold() for value in EMAIL.findall(text)})
        phones = sorted({re.sub(r"\s+", " ", value).strip(" .") for value in PHONE.findall(text)})
        rows.append({
            "candidate_id": candidate_id,
            "channel_id": candidate["channel_id"],
            "channel_target_stratum": candidate["channel_target_stratum"],
            "reference": candidate["reference"],
            "candidate_identity": candidate["candidate_identity"],
            "artifact": {
                "text_path": str(text_path),
                "text_sha256": text_row["text_sha256"],
                "visible_text_characters": text_row["visible_text_characters"],
                "canonical_urls_declared_in_capture": text_row["canonical_urls_declared_in_capture"],
                "contact_email_indicators": emails,
                "contact_phone_indicators": phones,
            },
            "automated_screen": {
                "opened_overlap": grouped["opened_overlap"],
                "candidate_internal_near_duplicate_hits": grouped["candidate_internal_near_duplicate_hits"],
                "technical_groups": grouped["technical_groups"],
            },
            "review_form": {
                "group_decision": "PENDING_MANUAL_REVIEW",
                "linked_candidate_ids": [],
                "linked_opened_record_keys": [],
                "positive_linkage_evidence": [],
                "identity_or_content_flags_for_downstream_review": [],
                "rationale": None,
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
            },
        })
    return {
        "packet_id": "ISI_TARGET_TEXT_CORPUS_V1_MANUAL_GROUP_REVIEW_PACKET_V1",
        "status": "FROZEN_UNREVIEWED_PACKET",
        "config": {"path": str(config_path), "sha256": sha(config_path)},
        "review_scope": config["review_scope"],
        "record_count": len(rows),
        "records": rows,
        "safety_contract": config["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load(args.config)
    output = Path(config["outputs"]["review_packet"])
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    packet = build(args.config)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(packet, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"packet_id": packet["packet_id"], "record_count": packet["record_count"], "output": str(output), "sha256": sha(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
