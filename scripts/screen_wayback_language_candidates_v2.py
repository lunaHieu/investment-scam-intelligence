"""Route corrected-language V2 captures through offline identity/content screening."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file
from src.isi.normalization.wayback_external_text import screen_archived_capture


def merge_profiles(profile_sets: list[list[dict[str, object]]]) -> list[dict[str, object]]:
    rows = [row for profile_set in profile_sets for row in profile_set]
    ids = [str(row["candidate_id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Language-profile inputs overlap candidate IDs")
    return sorted(rows, key=lambda row: str(row["candidate_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--queue-sha256", required=True)
    parser.add_argument("--profile", nargs=2, action="append", metavar=("PATH", "SHA256"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    if sha256_file(args.queue) != args.queue_sha256:
        raise ValueError("Combined queue SHA-256 mismatch")
    queue = {row["candidate_id"]: row for row in load_jsonl(args.queue)}
    profile_sets = []
    profile_inputs = []
    for raw_path, expected_hash in args.profile:
        path = Path(raw_path)
        if sha256_file(path) != expected_hash:
            raise ValueError(f"Profile SHA-256 mismatch: {path}")
        rows = load_jsonl(path)
        profile_sets.append(rows)
        profile_inputs.append({"path": str(path), "sha256": expected_hash, "record_count": len(rows)})
    profiles = merge_profiles(profile_sets)
    screened = []
    for row in profiles:
        candidate = queue.get(row["candidate_id"])
        if candidate is None:
            raise ValueError(f"Profile candidate missing from combined queue: {row['candidate_id']}")
        language = row["language_screening"]
        base = {
            "candidate_id": row["candidate_id"],
            "candidate_host": row["candidate_host"],
            "reference_branch": row["reference_branch"],
            "capture_stratum": row["capture_stratum"],
            "capture_path": row["capture_path"],
            "capture_sha256": row["capture_sha256"],
            "text_sha256": row["text_sha256"],
            "automatic_language_bucket": language["automatic_language_bucket"],
            "automatic_language_hint": language["automatic_language_hint"],
            "text_quality_state": language["text_quality_state"],
            "manual_language_confirmation_required": language["manual_confirmation_required"],
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        }
        if language["text_quality_state"] != "REVIEWABLE_VISIBLE_TEXT":
            base.update(
                {
                    "screening_decision": "REJECT_TEXT_QUALITY",
                    "screening_reasons": list(language["text_quality_reasons"]),
                    "identity_check": None,
                    "parking_marker_hits": [],
                    "solicitation_marker_hits": [],
                }
            )
        else:
            path = Path(row["capture_path"])
            if sha256_file(path) != row["capture_sha256"]:
                raise ValueError(f"Capture SHA-256 mismatch: {path}")
            profile, text, _ = screen_archived_capture(candidate=candidate, capture_path=path)
            if profile["text_sha256"] != row["text_sha256"]:
                raise ValueError(f"Visible-text SHA-256 mismatch: {row['candidate_id']}")
            base.update(
                {
                    "screening_decision": profile["screening_decision"],
                    "screening_reasons": profile["screening_reasons"],
                    "identity_check": profile["identity_check"],
                    "parking_marker_hits": profile["parking_marker_hits"],
                    "solicitation_marker_hits": profile["solicitation_marker_hits"],
                    "visible_text": text,
                }
            )
        screened.append(base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output, screened)
    decision_counts = Counter((row["reference_branch"], row["screening_decision"]) for row in screened)
    reviewable_language_counts = Counter(
        (row["reference_branch"], row["automatic_language_bucket"])
        for row in screened
        if row["screening_decision"] == "REVIEWABLE_OBSERVED_TEXT"
    )
    report = {
        "analysis_id": "WAYBACK_LANGUAGE_CANDIDATE_REVIEWABILITY_SCREENING_V2",
        "status": "OFFLINE_ROUTING_ONLY_MANUAL_REVIEW_REQUIRED",
        "inputs": {
            "combined_queue": {"path": str(args.queue), "sha256": args.queue_sha256},
            "corrected_language_profiles": profile_inputs,
        },
        "counts": {
            "candidate_count": len(screened),
            "decision_by_reference_branch": [
                {"reference_branch": branch, "screening_decision": decision, "count": count}
                for (branch, decision), count in sorted(decision_counts.items())
            ],
            "reviewable_automatic_language_by_reference_branch": [
                {"reference_branch": branch, "automatic_language_bucket": bucket, "count": count}
                for (branch, bucket), count in sorted(reviewable_language_counts.items())
            ],
            "labels_created": 0,
        },
        "output": {"path": str(args.output), "sha256": sha256_file(args.output)},
        "gates": {
            "manual_language_confirmation_required": True,
            "primary_evidence_review_required": True,
            "independent_blinded_second_review_required": True,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
