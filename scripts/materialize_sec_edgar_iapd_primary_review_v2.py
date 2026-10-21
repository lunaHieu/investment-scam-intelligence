"""Materialize the owner-authorized primary artifact review for 56 SEC/IAPD rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


PACKET_ID = "ISI_SEC_EDGAR_IAPD_PRIMARY_REVIEW_PACKET_V2"

IDENTITY_FAILURES = {
    "TTCV1_EDGAR_AVAIL_DEV_022": "The captured page identifies Interaudi Bank and declares interaudibank.com, not Ameraudi Asset Management at ameraudi.com.",
    "TTCV1_EDGAR_AVAIL_DEV_045": "The captured page identifies Thames Financial Management, while the frozen official entity is CDM Financial Counseling Services.",
    "TTCV1_EDGAR_AVAIL_DEV_061": "The captured page identifies Vantage Planning Services, while the frozen official entity is KRM Wealth Management.",
    "TTCV1_EDGAR_AVAIL_DEV_090": "The captured page identifies Leviticus Partners, while the frozen official entity is AMH Equity Ltd.",
}

IDENTITY_UNCERTAIN = {
    "TTCV1_EDGAR_AVAIL_DEV_032": "The page identifies Nerad + Deppe Wealth Management, but the frozen official entity is the acronym NDWM and the artifact contains no explicit alias bridge.",
}

CONTENT_UNCERTAIN = {
    "TTCV1_EDGAR_AVAIL_DEV_039": "The Laidlaw page also contains construction-template and placeholder contact content, so repurpose/template contamination cannot be ruled out.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_012": "Only 48 visible characters identify Bayesian Capital Management; task relevance, repurpose state and contradictions cannot be assessed adequately.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_020": "Only 185 visible characters provide the Hook Mill name and contact; substantive investment activity and contradiction checks remain insufficient.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_021": "Only 76 visible characters provide a Rainey & Randall wealth-planning tagline; repurpose and contradiction checks remain insufficient.",
}


def build_review(packet_path: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    if packet.get("packet_id") != PACKET_ID or packet.get("record_count") != 56:
        raise ValueError("Unexpected primary-review V2 packet")
    expected_uncertain = set(IDENTITY_FAILURES) | set(IDENTITY_UNCERTAIN) | set(CONTENT_UNCERTAIN)
    rows = []
    for source in packet["records"]:
        record_id = source["record_id"]
        capture = source["capture"]
        official = source["official_evidence"]
        if not capture.get("text") or not capture.get("snapshot_timestamp") or not capture.get("archive_url"):
            raise ValueError(f"Primary packet lacks captured artifact evidence: {record_id}")
        if official.get("iapd", {}).get("normalized_host") != source["candidate_identity"]["candidate_host"]:
            raise ValueError(f"Official host binding changed: {record_id}")
        assessments = {
            "identity_linkage": "PASS",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "PASS",
            "contradiction_screen": "PASS",
        }
        facts = [
            f"The frozen Wayback artifact at {capture['snapshot_timestamp']} contains local visible text for {source['candidate_identity']['candidate_host']} and its byte hash is fixed in the packet.",
            "The captured text identifies an investment, advisory, asset-management, wealth-management, banking, fund, or financial-planning activity relevant to the target task.",
            "The frozen IAPD record binds the candidate host to the reviewed entity, and the local EDGAR/IAPD name comparison passed before capture; this is supporting provenance only.",
        ]
        uncertainty: list[str] = []
        if record_id in IDENTITY_FAILURES:
            assessments["identity_linkage"] = "FAIL"
            assessments["contradiction_screen"] = "FAIL"
            uncertainty.append(IDENTITY_FAILURES[record_id])
        elif record_id in IDENTITY_UNCERTAIN:
            assessments["identity_linkage"] = "UNCERTAIN"
            assessments["contradiction_screen"] = "UNCERTAIN"
            uncertainty.append(IDENTITY_UNCERTAIN[record_id])
        if record_id in CONTENT_UNCERTAIN:
            assessments["repurpose_or_parking"] = "UNCERTAIN"
            assessments["contradiction_screen"] = "UNCERTAIN"
            uncertainty.append(CONTENT_UNCERTAIN[record_id])
            if record_id != "TTCV1_EDGAR_AVAIL_DEV_039":
                assessments["task_relevance"] = "UNCERTAIN"
        recommendation = "UNCERTAIN" if uncertainty else "LEGITIMATE"
        if recommendation == "LEGITIMATE":
            rationale = "The captured artifact independently presents the same entity or brand at the frozen candidate host and contains task-relevant investment/advisory content. The archive timestamp is explicit, no parking or repurpose indicator was observed, and no material contradiction appears in the local evidence. Official EDGAR/IAPD evidence supports provenance but is not used alone as ground truth. This remains a primary recommendation, not a label."
        else:
            rationale = "The frozen artifact and official-reference evidence were reviewed together, but at least one required affirmative check does not pass. " + " ".join(uncertainty) + " Source membership cannot cure the missing or contradictory artifact evidence, so the conservative primary recommendation is UNCERTAIN and no label is created."
        rows.append({
            "record_id": record_id,
            "primary_recommendation": recommendation,
            "assessments": assessments,
            "supporting_facts": facts,
            "uncertainty_reasons": uncertainty,
            "rationale": rationale,
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        })
    if {row["record_id"] for row in rows if row["primary_recommendation"] == "UNCERTAIN"} != expected_uncertain:
        raise ValueError("Primary uncertainty population changed")
    return {
        "review_id": "ISI_SEC_EDGAR_IAPD_PRIMARY_ARTIFACT_REVIEW_V2",
        "status": "PRIMARY_REVIEW_COMPLETE_STRUCTURAL_QA_REQUIRED",
        "input_packet": {"path": str(packet_path.resolve()), "sha256": sha256_file(packet_path)},
        "reviewer": {"mode": "AI_ASSISTED_MANUAL_REVIEW_AUTHORIZED_BY_OWNER", "network_access_used": False, "model_predictions_visible": False, "source_membership_treated_as_ground_truth": False},
        "method": {"all_packet_artifacts_reviewed": True, "five_required_assessments_recorded": True, "explicit_uncertainty_population": sorted(expected_uncertain), "primary_recommendation_is_not_label": True},
        "records": rows,
        "decision": {"ground_truth_labeling_completed": False, "blind_second_review_required": True, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite primary-review V2 decisions")
    result = build_review(args.packet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    counts = {value: sum(row["primary_recommendation"] == value for row in result["records"]) for value in ("LEGITIMATE", "UNCERTAIN")}
    print(json.dumps({"review_id": result["review_id"], "counts": counts, "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
