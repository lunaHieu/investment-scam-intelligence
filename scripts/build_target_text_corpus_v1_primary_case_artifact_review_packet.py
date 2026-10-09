"""Build a frozen local-evidence packet for primary case-and-artifact review."""

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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def by_record(rows: list[dict[str, Any]], field: str = "source_record_id") -> dict[str, dict[str, Any]]:
    return {str(row[field]): row for row in rows}


def build(config_path: Path) -> dict[str, Any]:
    config = load(config_path)
    if config.get("status") != "FROZEN_BEFORE_PRIMARY_CASE_ARTIFACT_REVIEW":
        raise ValueError("Primary case-and-artifact review protocol is not frozen")
    root = config_path.resolve().parents[1]
    paths: dict[str, Path] = {}
    for role, item in config["inputs"].items():
        path = resolve(root, item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError(f"Missing or changed input: {role}")
        paths[role] = path

    upstream = load(paths["manual_group_result_registry"])
    if upstream.get("decision", {}).get("primary_case_and_artifact_review_allowed") is not True:
        raise ValueError("Primary review has not been released by the group-review gate")
    if upstream.get("decision", {}).get("binary_labeling_completed") is not False:
        raise ValueError("Upstream unexpectedly claims binary labeling")

    group_review = load(paths["manual_group_primary_review"])
    group_rows = {row["candidate_id"]: row for row in group_review["records"]}
    if any(row.get("group_decision") != "KEEP_PROVISIONALLY_DISTINCT" for row in group_rows.values()):
        raise ValueError("Non-distinct or unresolved group entered primary review")
    queue = {row["candidate_id"]: row for row in load_jsonl(paths["candidate_queue"])}
    manifest = {
        row["candidate_id"]: row
        for row in load_jsonl(paths["exact_text_manifest"])
        if row.get("minimum_content_passed") is True
    }
    cftc = by_record(load_jsonl(paths["cftc_red_reference"]))
    iosco = by_record(load_jsonl(paths["iosco_warning_reference"]))
    iapd = by_record(load_jsonl(paths["sec_registration_reference"]))
    edgar_shortlist = by_record(load_jsonl(paths["sec_edgar_iapd_shortlist"]), "cik")

    if set(group_rows) != set(manifest) or len(manifest) != config["expected_review_population"]:
        raise ValueError("Primary review population changed")

    records = []
    for candidate_id in sorted(manifest):
        candidate = queue[candidate_id]
        text_row = manifest[candidate_id]
        text_path = Path(text_row["text_path"])
        if not text_path.is_file() or sha(text_path) != text_row["text_sha256"]:
            raise ValueError(f"Missing or changed exact text: {candidate_id}")
        reference = candidate["reference"]
        source_id = reference["source_id"]
        source_record_id = str(reference["source_record_id"])
        evidence: dict[str, Any]
        if source_id == "cftc_red_list":
            evidence = {"warning_reference": cftc[source_record_id]}
        elif source_id == "iosco_i_scan":
            evidence = {"warning_reference": iosco[source_record_id]}
        elif source_id == "sec_iapd":
            evidence = {"registration_reference": iapd[source_record_id]}
        elif source_id == "sec_edgar_company_submissions":
            crosswalk = edgar_shortlist[source_record_id]
            iapd_id = str(crosswalk["iapd_source_record_id"])
            evidence = {
                "edgar_iapd_crosswalk": crosswalk,
                "registration_reference": iapd[iapd_id],
                "crosswalk_caution": "EDGAR entity identity is supporting provenance only; the IAPD entity and captured artifact must independently align.",
            }
        else:
            raise ValueError(f"Unsupported evidence source: {source_id}")
        records.append({
            "candidate_id": candidate_id,
            "channel_id": candidate["channel_id"],
            "channel_target_stratum": candidate["channel_target_stratum"],
            "candidate_identity": candidate["candidate_identity"],
            "capture": {
                "archive_url": text_row["archive_url"],
                "snapshot_timestamp": text_row["snapshot_timestamp"],
                "text_path": str(text_path),
                "text_sha256": text_row["text_sha256"],
                "visible_text_characters": text_row["visible_text_characters"],
                "text": text_path.read_text(encoding="utf-8"),
            },
            "official_evidence": evidence,
            "group_review": {
                "decision": group_rows[candidate_id]["group_decision"],
                "downstream_flags": group_rows[candidate_id]["identity_or_content_flags_for_downstream_review"],
            },
            "review_form": {
                "primary_recommendation": "PENDING_PRIMARY_REVIEW",
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
    return {
        "packet_id": "ISI_TARGET_TEXT_CORPUS_V1_PRIMARY_CASE_ARTIFACT_REVIEW_PACKET_V1",
        "status": "FROZEN_UNREVIEWED_PACKET",
        "config": {"path": str(config_path), "sha256": sha(config_path)},
        "review_scope": config["review_scope"],
        "record_count": len(records),
        "records": records,
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
