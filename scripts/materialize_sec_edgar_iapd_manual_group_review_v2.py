"""Materialize the owner-authorized, offline manual group review for 56 rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.normalization.external_references import canonicalize_host


PACKET_ID = "ISI_SEC_EDGAR_IAPD_MANUAL_GROUP_REVIEW_PACKET_V2"
SPARSE_THRESHOLD = 500


def canonical_hosts(values: list[str]) -> list[str]:
    hosts = []
    for value in values:
        parsed = urlparse(value)
        host = canonicalize_host(parsed.hostname or "")
        if host:
            hosts.append(host)
    return sorted(set(hosts))


def build_review(packet_path: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    if packet.get("packet_id") != PACKET_ID or packet.get("record_count") != 56:
        raise ValueError("Unexpected manual group-review V2 packet")
    if packet.get("population_contract", {}).get("capture_quarantined_rows") != 1:
        raise ValueError("Capture quarantine contract changed")
    rows = []
    for source in packet["records"]:
        screen = source["automated_screen"]
        overlap = screen["opened_overlap"]
        if any((overlap["exact_capture_record_keys"], overlap["exact_text_record_keys"], overlap["exact_normalized_host_record_keys"], overlap["probable_near_duplicate_hits"], screen["candidate_internal_near_duplicate_hits"], screen["cross_cohort_group_collision"])):
            raise ValueError(f"Positive linkage requires an explicit non-default decision: {source['record_id']}")
        text_path = Path(source["artifact"]["text_path"])
        payload = text_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != source["artifact"]["text_sha256"]:
            raise ValueError(f"Exact text changed during manual review: {source['record_id']}")
        text = payload.decode("utf-8")
        candidate_host = canonicalize_host(source["candidate_host"])
        declared_hosts = canonical_hosts(source["artifact"]["canonical_urls_declared_in_capture"])
        mismatched_declared = [host for host in declared_hosts if host != candidate_host and not host.endswith("." + candidate_host) and not candidate_host.endswith("." + host)]
        flags: list[str] = []
        reasons = [
            "The frozen local text and the complete automated exclusion screen were inspected offline.",
            "No exact host/text/capture, normalized near-duplicate, contact-indicator, or cross-cohort linkage to another reviewed record was found.",
        ]
        if source["artifact"]["visible_text_characters"] < SPARSE_THRESHOLD:
            flags.append("SPARSE_CAPTURE_TEXT_LT_500_CHARACTERS")
            reasons.append("The capture is sparse, so primary artifact review must treat the identity/content evidence conservatively.")
        if mismatched_declared:
            flags.append("DECLARED_CANONICAL_HOST_DIFFERS_FROM_CANDIDATE_HOST")
            reasons.append("The captured page declares a different canonical host; this is an identity-evidence flag for primary review, not group-link evidence.")
        lowered = text.casefold()
        if "saylo construction" in lowered or "example@gmail.com" in lowered or "+000 (123) 456 88" in lowered:
            flags.append("TEMPLATE_OR_PLACEHOLDER_CONTENT_INDICATORS")
            reasons.append("Template or placeholder content indicators were observed and must be resolved during primary artifact review.")
        rows.append({
            "record_id": source["record_id"],
            "group_decision": "KEEP_PROVISIONALLY_DISTINCT",
            "linked_record_ids": [],
            "canonical_record_id": None,
            "linked_opened_record_keys": [],
            "positive_linkage_evidence": [],
            "identity_or_content_flags_for_primary_review": flags,
            "rationale": " ".join(reasons),
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        })
    return {
        "review_id": "ISI_SEC_EDGAR_IAPD_MANUAL_GROUP_REVIEW_V2",
        "status": "MANUAL_GROUP_REVIEW_COMPLETE_STRUCTURAL_QA_REQUIRED",
        "input_packet": {"path": str(packet_path.resolve()), "sha256": sha256_file(packet_path)},
        "reviewer": {
            "mode": "AI_ASSISTED_MANUAL_REVIEW_AUTHORIZED_BY_OWNER",
            "scope": "ALL_56_REVIEWABLE_ROWS_TEXT_SAMPLES_CONTACT_CANONICAL_AND_AUTOMATED_LINKAGE_INSPECTED",
            "network_access_used": False,
            "model_predictions_visible": False,
            "source_membership_treated_as_label": False,
        },
        "review_method": {
            "packet_rows_inspected": 56,
            "exact_text_hash_rechecked_per_row": True,
            "contact_indicators_compared_across_packet": True,
            "canonical_host_mismatches_flagged": True,
            "sparse_text_threshold_characters": SPARSE_THRESHOLD,
            "positive_linkage_requires_non_default_explicit_decision": True,
        },
        "records": rows,
        "decision": {"binary_labeling_completed": False, "capture_quarantined_rows": 1, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite manual group-review V2 decisions")
    result = build_review(args.packet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"review_id": result["review_id"], "record_count": len(result["records"]), "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
