"""Screen matched Wayback captures and build a label-blind second-review packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from src.isi.normalization.external_text import extract_visible_text
from src.isi.normalization.wayback_external_text import (
    decode_archived_payload,
    screen_archived_capture,
    snapshot_timestamp_iso,
)
from validate_external_text_intake import sha256_file


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"Blank JSONL line: {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row is not an object: {line_number}")
        rows.append(value)
    return rows


def stable_key(seed: str, candidate_id: str) -> str:
    return hashlib.sha256(f"{seed}|{candidate_id}".encode("utf-8")).hexdigest()


def blind_id(seed: str, candidate_id: str) -> str:
    return f"BRV1_{stable_key(seed, candidate_id)[:12].upper()}"


def assert_blind_packet(packet: dict[str, object]) -> None:
    prohibited = {
        "reference_status",
        "source_case_id",
        "ground_truth_status",
        "model_prediction",
        "score_label_1",
        "first_review",
    }

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).casefold() in prohibited:
                    raise ValueError(f"Blind packet leaks prohibited field: {key}")
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(packet)


def build_confirmed_candidate(
    queue_item: dict[str, object], source_record: dict[str, object], raw_root: Path
) -> dict[str, object]:
    artifact = source_record["artifact"]
    existing = queue_item["existing_capture"]
    capture_path = Path(str(existing["path"]))
    if not capture_path.is_file() or sha256_file(capture_path) != existing["sha256"]:
        raise ValueError(f"Confirmed raw capture missing or changed: {queue_item['candidate_id']}")
    decoded, transport = decode_archived_payload(capture_path.read_bytes())
    text, _ = extract_visible_text(decoded)
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if text_hash != artifact["text_sha256"] or text != artifact["text"]:
        raise ValueError(f"Confirmed normalized text does not reproduce: {queue_item['candidate_id']}")
    return {
        "candidate_id": queue_item["candidate_id"],
        "source_case_id": queue_item["source_case_id"],
        "reference_status": "CONFIRMED",
        "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
        "eligible_for_blind_second_review": True,
        "screening": {
            "decision": "REUSE_HASH_PINNED_RECONCILED_CAPTURE",
            "transport_decoding": transport,
            "visible_text_characters": len(text),
            "capture_sha256_verified": True,
            "text_sha256_verified": True,
        },
        "artifact": {
            "text": text,
            "text_sha256": text_hash,
            "url": artifact["url"],
            "content_observed_at": artifact["content_observed_at"],
            "source_capture_path": str(capture_path),
            "source_capture_sha256": existing["sha256"],
        },
        "evidence": queue_item["reference_evidence"],
    }


def build_legitimate_candidate(
    queue_item: dict[str, object], capture_item: dict[str, object], raw_root: Path
) -> dict[str, object]:
    capture_path = Path(str(capture_item.get("path", "")))
    if not capture_path.is_file() or sha256_file(capture_path) != capture_item.get("sha256"):
        raise ValueError(f"Legitimate raw capture missing or changed: {queue_item['candidate_id']}")
    if not capture_path.resolve().is_relative_to(raw_root.resolve()):
        raise ValueError(f"Raw capture escaped raw root: {capture_path}")
    profile, text, _ = screen_archived_capture(candidate=queue_item, capture_path=capture_path)
    observed_date = datetime.strptime(str(capture_item["snapshot_timestamp"]), "%Y%m%d%H%M%S").date()
    official_reference = queue_item.get("sec_reference") or queue_item.get("official_reference")
    if not isinstance(official_reference, dict):
        raise ValueError(f"Missing SEC/IAPD reference: {queue_item['candidate_id']}")
    registration_date = date.fromisoformat(str(official_reference["registration"]["date"]))
    predates_registration = observed_date < registration_date
    eligible = profile["screening_decision"] == "REVIEWABLE_OBSERVED_TEXT" and not predates_registration
    evidence = list(queue_item.get("reference_evidence", []))
    if not evidence:
        evidence.append(
            {
                "evidence_type": "official_registry",
                "source_id": "sec_iapd",
                "source_url": official_reference.get("url"),
                "supports": ["IDENTITY", "REGISTRATION"],
            }
        )
    evidence.append(
        {
            "evidence_type": "web_snapshot",
            "source_id": "internet_archive",
            "source_url": capture_item.get("final_archive_url") or capture_item["requested_archive_url"],
            "supports": ["IDENTITY", "DOMAIN_LINK", "OBSERVED_TEXT"],
        }
    )
    return {
        "candidate_id": queue_item["candidate_id"],
        "source_case_id": queue_item["source_case_id"],
        "reference_status": queue_item.get("reference_status", "UNADJUDICATED"),
        "target_branch": "LEGITIMATE",
        "prior_reconciliation_status": queue_item.get("prior_reconciliation_status", "RECONCILED"),
        "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
        "eligible_for_blind_second_review": eligible,
        "screening": {
            **profile,
            "snapshot_predates_registration": predates_registration,
            "registration_date": str(registration_date),
        },
        "artifact": {
            "text": text,
            "text_sha256": profile["text_sha256"],
            "url": capture_item.get("final_archive_url") or capture_item["requested_archive_url"],
            "content_observed_at": snapshot_timestamp_iso(str(capture_item["snapshot_timestamp"])),
            "source_capture_path": str(capture_path),
            "source_capture_sha256": capture_item["sha256"],
        },
        "evidence": evidence,
    }


def build_blind_item(candidate: dict[str, object], seed: str) -> tuple[dict, dict]:
    identifier = blind_id(seed, candidate["candidate_id"])
    blind = {
        "blind_review_id": identifier,
        "capture_stratum": candidate["capture_stratum"],
        "artifact": candidate["artifact"],
        "evidence": candidate["evidence"],
        "review_contract": {
            "allowed_decisions": ["CONFIRMED", "LEGITIMATE", "UNCERTAIN", "REJECT_CAPTURE"],
            "must_reconcile_artifact_identity_with_evidence": True,
            "must_check_capture_quality_and_domain_repurpose": True,
            "must_record_contradictions": True,
            "decision_confidence": ["HIGH", "MEDIUM", "LOW"],
        },
        "second_review": {
            "status": "PENDING",
            "decision": None,
            "confidence": None,
            "rationale": None,
            "evidence_checks": [],
            "contradictions": [],
            "reviewer": None,
            "reviewed_at": None,
        },
    }
    mapping = {
        "blind_review_id": identifier,
        "candidate_id": candidate["candidate_id"],
        "source_case_id": candidate["source_case_id"],
        "reference_status": candidate["reference_status"],
        "artifact_text_sha256": candidate["artifact"]["text_sha256"],
        "capture_sha256": candidate["artifact"]["source_capture_sha256"],
    }
    return blind, mapping


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--reconciled-intake", type=Path, required=True)
    parser.add_argument("--supplement-candidates", type=Path, required=True)
    parser.add_argument("--supplement-first-review", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_paths = {
        "candidates": args.output_dir / "matched_wayback_candidates_v1.jsonl",
        "packet": args.output_dir / "blind_second_review_packet_v1.json",
        "mapping": args.output_dir / "blind_second_review_mapping_v1.jsonl",
        "report": args.output_dir / "preparation_report_v1.json",
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen output: {existing[0]}")
    config = load_json(args.config)
    if config.get("protocol_id") != "EXTERNAL_TEXT_MATCHED_WAYBACK_EXPANSION_V1":
        raise ValueError("Unexpected protocol config")
    queue = load_jsonl(args.queue)
    capture_report = load_json(args.capture_report)
    intake = load_json(args.reconciled_intake)
    source_records = {item["case_id"]: item for item in intake["records"]}
    capture_items = {
        item["candidate_id"]: item
        for item in capture_report.get("results", [])
        if item.get("outcome") == "CAPTURED"
    }
    candidates = []
    for item in queue:
        if item["reference_status"] == "CONFIRMED":
            candidates.append(
                build_confirmed_candidate(item, source_records[item["source_case_id"]], args.raw_root)
            )
        else:
            capture = capture_items.get(item["candidate_id"])
            if capture is None:
                continue
            candidates.append(build_legitimate_candidate(item, capture, args.raw_root))

    supplement_candidates = {
        item["candidate_id"]: item for item in load_jsonl(args.supplement_candidates)
    }
    supplement_review = load_json(args.supplement_first_review)
    accepted_supplement_count = 0
    for review in supplement_review.get("reviews", []):
        if not review.get("ready_for_independent_second_review"):
            continue
        candidate = supplement_candidates.get(review["candidate_id"])
        if candidate is None:
            raise ValueError(f"Missing supplemental candidate: {review['candidate_id']}")
        if (
            candidate["artifact"]["text_sha256"] != review["artifact_text_sha256"]
            or candidate["artifact"]["source_capture_sha256"] != review["capture_sha256"]
        ):
            raise ValueError(f"Supplemental first-review artifact mismatch: {review['candidate_id']}")
        candidate = dict(candidate)
        candidate["reference_status"] = "LEGITIMATE"
        candidate["prior_reconciliation_status"] = "AI_PRIMARY_REVIEW_COMPLETE"
        candidate["primary_review"] = {
            "review_id": supplement_review.get("review_id"),
            "decision": review["decision"],
            "confidence": review["confidence"],
            "review_type": review["review_type"],
            "independent_human_review_claimed": False,
        }
        candidates.append(candidate)
        accepted_supplement_count += 1

    seed = str(config["selection_seed"])
    target = int(config["target_per_class"])
    selected = []
    for status in ("CONFIRMED", "LEGITIMATE"):
        eligible = [
            item
            for item in candidates
            if item["reference_status"] == status and item["eligible_for_blind_second_review"]
        ]
        eligible.sort(key=lambda item: stable_key(seed, item["candidate_id"]))
        selected.extend(eligible[:target])
    blind_items = []
    mappings = []
    for candidate in selected:
        blind, mapping = build_blind_item(candidate, seed)
        blind_items.append(blind)
        mappings.append(mapping)
    blind_items.sort(key=lambda item: item["blind_review_id"])
    mappings.sort(key=lambda item: item["blind_review_id"])
    packet = {
        "packet_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_BLIND_SECOND_REVIEW_V1",
        "status": "PENDING_INDEPENDENT_SECOND_REVIEW",
        "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
        "blinding": {
            "first_review_decisions_removed": True,
            "model_outputs_removed": True,
            "original_case_ids_removed": True,
            "evidence_sources_visible": True,
        },
        "instructions": [
            "Assess the archived artifact and its evidence without consulting first-review or model outputs.",
            "CONFIRMED requires identity/domain alignment with an official warning and no unresolved repurpose contradiction.",
            "LEGITIMATE requires identity/domain alignment with the registration reference and no unresolved impersonation/adverse-evidence contradiction.",
            "Use UNCERTAIN or REJECT_CAPTURE whenever the evidence or capture is insufficient.",
        ],
        "items": blind_items,
    }
    assert_blind_packet(packet)
    counts = {
        status: {
            "candidate_count": sum(item["reference_status"] == status for item in candidates),
            "eligible_count": sum(
                item["reference_status"] == status and item["eligible_for_blind_second_review"]
                for item in candidates
            ),
            "selected_count": sum(item["reference_status"] == status for item in selected),
        }
        for status in ("CONFIRMED", "LEGITIMATE")
    }
    gate_open = all(values["selected_count"] == target for values in counts.values())
    report = {
        "analysis_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_SECOND_REVIEW_PREPARATION_V1",
        "status": "BLIND_SECOND_REVIEW_READY" if gate_open else "MATCHED_CAPTURE_GATE_BLOCKED",
        "inputs": {
            "config": {"path": str(args.config), "sha256": sha256_file(args.config)},
            "queue": {"path": str(args.queue), "sha256": sha256_file(args.queue)},
            "capture_report": {"path": str(args.capture_report), "sha256": sha256_file(args.capture_report)},
            "reconciled_intake": {"path": str(args.reconciled_intake), "sha256": sha256_file(args.reconciled_intake)},
            "supplement_candidates": {"path": str(args.supplement_candidates), "sha256": sha256_file(args.supplement_candidates)},
            "supplement_first_review": {"path": str(args.supplement_first_review), "sha256": sha256_file(args.supplement_first_review)},
        },
        "counts": counts,
        "gate": {
            "target_per_class": target,
            "matched_capture_gate_open": gate_open,
            "second_review_complete": False,
            "benchmark_eligible_count": 0,
            "accepted_supplement_first_review_count": accepted_supplement_count,
        },
        "screening_failures": [
            {
                "candidate_id": item["candidate_id"],
                "reference_status": item["reference_status"],
                "screening": item["screening"],
            }
            for item in candidates
            if not item["eligible_for_blind_second_review"]
        ],
        "safety_contract": {
            "network_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "first_review_decisions_exposed_to_reviewer": False,
            "training_allowed": False,
            "deployment_allowed": False,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_paths["candidates"], candidates)
    output_paths["packet"].write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_jsonl(output_paths["mapping"], mappings)
    report["outputs"] = {
        role: {"path": str(path), "sha256": sha256_file(path)}
        for role, path in output_paths.items()
        if role != "report"
    }
    output_paths["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
