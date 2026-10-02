"""Freeze the V2 primary-review packet without creating benchmark labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl
from src.isi.normalization.external_references import sha256_file


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_primary_packet(
    queue_rows: list[dict[str, object]],
    screening_rows: list[dict[str, object]],
    reference_rows_by_key: dict[tuple[str, str], dict[str, object]] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    queue = {str(row["candidate_id"]): row for row in queue_rows}
    items: list[dict[str, object]] = []
    mappings: list[dict[str, object]] = []
    for screened in screening_rows:
        if screened.get("screening_decision") != "REVIEWABLE_OBSERVED_TEXT":
            continue
        candidate_id = str(screened["candidate_id"])
        candidate = queue.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Screened candidate is absent from queue: {candidate_id}")
        if screened.get("ground_truth_status") != "UNCERTAIN" or screened.get("label_created") is not False:
            raise ValueError(f"Screening row already claims a label: {candidate_id}")
        reference_record = None
        if reference_rows_by_key is not None:
            reference_key = (str(candidate["source_id"]), str(candidate["source_record_id"]))
            reference_record = reference_rows_by_key.get(reference_key)
            if reference_record is None:
                raise ValueError(f"Official reference row is absent: {candidate_id}")
            if str(screened["candidate_host"]) not in reference_record.get("observed_hosts", []):
                raise ValueError(f"Candidate host is absent from official reference row: {candidate_id}")
        items.append(
            {
                "candidate_id": candidate_id,
                "candidate_host": screened["candidate_host"],
                "capture_stratum": screened["capture_stratum"],
                "artifact": {
                    "visible_text": screened["visible_text"],
                    "text_sha256": screened["text_sha256"],
                    "capture_path": screened["capture_path"],
                    "capture_sha256": screened["capture_sha256"],
                },
                "automatic_language_screening": {
                    "bucket": screened["automatic_language_bucket"],
                    "hint": screened["automatic_language_hint"],
                    "manual_confirmation_required": True,
                },
                "identity_screening": screened["identity_check"],
                "official_reference": candidate["official_reference"],
                "official_reference_record": reference_record,
                "entity_name_keys": candidate["entity_name_keys"],
                "review_contract": {
                    "allowed_language_decisions": [
                        "ENGLISH",
                        "NON_ENGLISH",
                        "MIXED_OR_UNDETERMINED",
                        "UNREADABLE",
                    ],
                    "allowed_evidence_decisions": [
                        "CONFIRMED",
                        "LEGITIMATE",
                        "UNCERTAIN",
                        "REJECT_CAPTURE",
                    ],
                    "allowed_confidence": ["HIGH", "MEDIUM", "LOW"],
                    "must_reconcile_archived_identity_with_official_reference": True,
                    "must_check_repurpose_or_impersonation_contradictions": True,
                    "warning_or_registry_text_must_not_become_model_input": True,
                },
            }
        )
        mappings.append(
            {
                "candidate_id": candidate_id,
                "reference_branch": candidate["reference_branch"],
                "source_case_id": candidate["source_case_id"],
                "text_sha256": screened["text_sha256"],
                "capture_sha256": screened["capture_sha256"],
            }
        )
    items.sort(key=lambda row: str(row["candidate_id"]))
    mappings.sort(key=lambda row: str(row["candidate_id"]))
    packet = {
        "packet_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_PRIMARY_REVIEW_V2",
        "status": "PENDING_AI_PRIMARY_REVIEW_NOT_HUMAN",
        "instructions": [
            "Read the archived visible text and reconcile its identity/domain with the official reference.",
            "Confirm language manually; automatic language output is routing assistance only.",
            "A warning reference is evidence for review, not a criminal conviction or an automatic scam label.",
            "A registration reference is not proof that the archived site is operated by the registered firm.",
            "Use UNCERTAIN or REJECT_CAPTURE when identity, timing, repurpose, impersonation, or content quality remains unresolved.",
            "Do not consult or run any model prediction or score.",
        ],
        "items": items,
    }
    return packet, mappings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--queue-sha256", required=True)
    parser.add_argument("--screening", type=Path, required=True)
    parser.add_argument("--screening-sha256", required=True)
    parser.add_argument(
        "--reference-index",
        nargs=2,
        action="append",
        metavar=("PATH", "SHA256"),
        default=[],
        help="Hash-pinned official-reference JSONL; may be repeated.",
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.packet, args.mapping, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    for path, expected in (
        (args.config, args.config_sha256),
        (args.queue, args.queue_sha256),
        (args.screening, args.screening_sha256),
    ):
        if sha256_file(path) != expected:
            raise ValueError(f"Input SHA-256 mismatch: {path}")
    reference_inputs = [(Path(path), expected) for path, expected in args.reference_index]
    for path, expected in reference_inputs:
        if sha256_file(path) != expected:
            raise ValueError(f"Input SHA-256 mismatch: {path}")
    reference_rows_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for path, _ in reference_inputs:
        for row in load_jsonl(path):
            key = (str(row["source_id"]), str(row["source_record_id"]))
            if key in reference_rows_by_key:
                raise ValueError(f"Duplicate official reference key: {key}")
            reference_rows_by_key[key] = row
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("protocol_id") != "EXTERNAL_TEXT_WAYBACK_LANGUAGE_EXPANSION_V2":
        raise ValueError("Unexpected protocol config")
    packet, mappings = build_primary_packet(
        load_jsonl(args.queue),
        load_jsonl(args.screening),
        reference_rows_by_key if reference_inputs else None,
    )
    args.packet.parent.mkdir(parents=True, exist_ok=True)
    args.packet.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.mapping.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.mapping, mappings)
    counts: dict[str, int] = {}
    for row in mappings:
        branch = str(row["reference_branch"])
        counts[branch] = counts.get(branch, 0) + 1
    report = {
        "analysis_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_PRIMARY_REVIEW_PREPARATION_V2",
        "status": "AI_PRIMARY_REVIEW_PACKET_READY_NOT_HUMAN",
        "inputs": {
            "config": {"path": str(args.config), "sha256": args.config_sha256},
            "queue": {"path": str(args.queue), "sha256": args.queue_sha256},
            "screening": {"path": str(args.screening), "sha256": args.screening_sha256},
            "reference_indices": [
                {"path": str(path), "sha256": expected}
                for path, expected in reference_inputs
            ],
        },
        "counts": {"review_items": len(packet["items"]), "by_reference_branch": counts},
        "outputs": {
            "packet": {"path": str(args.packet), "sha256": sha256_file(args.packet)},
            "mapping": {"path": str(args.mapping), "sha256": sha256_file(args.mapping)},
        },
        "safety_contract": {
            "network_operations": 0,
            "model_scoring_operations": 0,
            "labels_created": 0,
            "independent_human_review_claimed": False,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
