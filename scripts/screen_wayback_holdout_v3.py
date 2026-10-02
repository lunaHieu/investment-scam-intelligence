"""Extract and screen verified Wayback holdout V3 captures entirely offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file
from src.isi.normalization.language_screening_v2 import screen_html_language_v2
from src.isi.normalization.wayback_external_text import screen_archived_capture


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--queue-sha256", required=True)
    parser.add_argument("--usable-captures", type=Path, required=True)
    parser.add_argument("--usable-captures-sha256", required=True)
    parser.add_argument("--profiles-output", type=Path, required=True)
    parser.add_argument("--screening-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.profiles_output, args.screening_output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    if sha256_file(args.queue) != args.queue_sha256:
        raise ValueError("Candidate queue SHA-256 mismatch")
    if sha256_file(args.usable_captures) != args.usable_captures_sha256:
        raise ValueError("Usable capture view SHA-256 mismatch")
    queue = {row["candidate_id"]: row for row in load_jsonl(args.queue)}
    usable = json.loads(args.usable_captures.read_text(encoding="utf-8"))
    if usable.get("report_id") != "WAYBACK_HOLDOUT_BALANCED_USABLE_CAPTURE_VIEW_V3":
        raise ValueError("Unexpected usable capture view")
    profiles = []
    screened = []
    for item in usable["results"]:
        if item.get("outcome") != "CAPTURED":
            raise ValueError("Usable view contains a non-captured row")
        candidate = queue.get(item["candidate_id"])
        if candidate is None:
            raise ValueError(f"Capture not found in V3 queue: {item['candidate_id']}")
        path = Path(str(item["path"]))
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Capture SHA-256 mismatch: {path}")
        language, text = screen_html_language_v2(path.read_bytes())
        text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        profile = {
            "candidate_id": item["candidate_id"],
            "candidate_host": item["candidate_host"],
            "reference_branch": candidate["reference_branch"],
            "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
            "capture_path": str(path),
            "capture_sha256": item["sha256"],
            "text_sha256": text_sha,
            "visible_text": text,
            "language_screening": language,
            "language_review_status": (
                "PENDING_INDEPENDENT_REVIEW_CONFIRMATION"
                if language["manual_confirmation_required"]
                else "BLOCKED_BY_TEXT_QUALITY"
            ),
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
            "model_scoring_eligible": "NO_BEFORE_FROZEN_BENCHMARK_AND_OWNER_ACCEPTANCE",
        }
        base = {
            "candidate_id": item["candidate_id"],
            "candidate_host": item["candidate_host"],
            "reference_branch": candidate["reference_branch"],
            "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
            "capture_path": str(path),
            "capture_sha256": item["sha256"],
            "text_sha256": text_sha,
            "automatic_language_bucket": language["automatic_language_bucket"],
            "automatic_language_hint": language["automatic_language_hint"],
            "text_quality_state": language["text_quality_state"],
            "manual_language_confirmation_required": language["manual_confirmation_required"],
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
            "model_scoring_eligible": "NO_BEFORE_FROZEN_BENCHMARK_AND_OWNER_ACCEPTANCE",
        }
        if language["text_quality_state"] != "REVIEWABLE_VISIBLE_TEXT":
            base.update({
                "screening_decision": "REJECT_TEXT_QUALITY",
                "screening_reasons": list(language["text_quality_reasons"]),
                "identity_check": None,
                "parking_marker_hits": [],
                "solicitation_marker_hits": [],
            })
        else:
            content_profile, screened_text, _ = screen_archived_capture(
                candidate=candidate, capture_path=path
            )
            screened_sha = hashlib.sha256(screened_text.encode("utf-8")).hexdigest()
            if screened_sha != text_sha or content_profile["text_sha256"] != text_sha:
                raise ValueError(f"Visible-text extraction mismatch: {item['candidate_id']}")
            base.update({
                "screening_decision": content_profile["screening_decision"],
                "screening_reasons": content_profile["screening_reasons"],
                "identity_check": content_profile["identity_check"],
                "parking_marker_hits": content_profile["parking_marker_hits"],
                "solicitation_marker_hits": content_profile["solicitation_marker_hits"],
                "visible_text": text,
            })
        profiles.append(profile)
        screened.append(base)
    profiles.sort(key=lambda row: row["candidate_id"])
    screened.sort(key=lambda row: row["candidate_id"])
    args.profiles_output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.profiles_output, profiles)
    write_jsonl(args.screening_output, screened)
    quality_counts = Counter(
        (row["reference_branch"], row["language_screening"]["text_quality_state"])
        for row in profiles
    )
    decision_counts = Counter(
        (row["reference_branch"], row["screening_decision"]) for row in screened
    )
    reviewable_languages = Counter(
        (row["reference_branch"], row["automatic_language_bucket"])
        for row in screened if row["screening_decision"] == "REVIEWABLE_OBSERVED_TEXT"
    )
    report = {
        "analysis_id": "WAYBACK_HOLDOUT_OFFLINE_SCREENING_V3",
        "status": "OFFLINE_ROUTING_ONLY_INDEPENDENT_REVIEW_REQUIRED",
        "inputs": {
            "queue": {"path": str(args.queue), "sha256": args.queue_sha256},
            "usable_captures": {
                "path": str(args.usable_captures),
                "sha256": args.usable_captures_sha256,
            },
        },
        "counts": {
            "profile_count": len(profiles),
            "text_quality_by_reference_branch": [
                {"reference_branch": branch, "text_quality_state": state, "count": count}
                for (branch, state), count in sorted(quality_counts.items())
            ],
            "screening_decision_by_reference_branch": [
                {"reference_branch": branch, "screening_decision": decision, "count": count}
                for (branch, decision), count in sorted(decision_counts.items())
            ],
            "reviewable_automatic_language_by_reference_branch": [
                {"reference_branch": branch, "automatic_language_bucket": bucket, "count": count}
                for (branch, bucket), count in sorted(reviewable_languages.items())
            ],
            "labels_created": 0,
        },
        "outputs": {
            "profiles": {"path": str(args.profiles_output), "sha256": sha256_file(args.profiles_output)},
            "screening": {"path": str(args.screening_output), "sha256": sha256_file(args.screening_output)},
        },
        "gates": {
            "primary_evidence_review_required": True,
            "independent_blinded_second_review_required": True,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "raw_files_modified": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
