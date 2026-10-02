"""Extract visible text and create manual language-screening records from V2 captures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file
from src.isi.normalization.language_screening import screen_html_language


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--queue-sha256", required=True)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--capture-report-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    if sha256_file(args.queue) != args.queue_sha256:
        raise ValueError("Candidate queue SHA-256 mismatch")
    if sha256_file(args.capture_report) != args.capture_report_sha256:
        raise ValueError("Capture report SHA-256 mismatch")

    queue = {row["candidate_id"]: row for row in load_jsonl(args.queue)}
    capture_report = json.loads(args.capture_report.read_text(encoding="utf-8"))
    captured = [row for row in capture_report["results"] if row["outcome"] == "CAPTURED"]
    profiles = []
    for item in captured:
        candidate = queue.get(item["candidate_id"])
        if candidate is None:
            raise ValueError(f"Capture is not in the frozen queue: {item['candidate_id']}")
        path = Path(item["path"])
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Capture SHA-256 mismatch: {path}")
        screening, text = screen_html_language(path.read_bytes())
        profiles.append(
            {
                "candidate_id": item["candidate_id"],
                "candidate_host": item["candidate_host"],
                "reference_branch": candidate["reference_branch"],
                "capture_stratum": "WAYBACK_ARCHIVED_HOMEPAGE_HTML",
                "capture_path": str(path),
                "capture_sha256": item["sha256"],
                "text_sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
                "visible_text": text,
                "language_screening": screening,
                "language_review_status": "PENDING_MANUAL_CONFIRMATION",
                "ground_truth_status": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
            }
        )
    profiles.sort(key=lambda row: row["candidate_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output, profiles)
    bucket_counts: dict[str, dict[str, int]] = {}
    for row in profiles:
        bucket = row["language_screening"]["automatic_language_bucket"]
        branch = row["reference_branch"]
        bucket_counts.setdefault(bucket, {})[branch] = bucket_counts.setdefault(bucket, {}).get(branch, 0) + 1
    report = {
        "analysis_id": "WAYBACK_LANGUAGE_SCREENING_V2",
        "status": "AUTOMATIC_SCREENING_ONLY_MANUAL_CONFIRMATION_REQUIRED",
        "inputs": {
            "queue": {"path": str(args.queue), "sha256": args.queue_sha256},
            "capture_report": {"path": str(args.capture_report), "sha256": args.capture_report_sha256},
        },
        "counts": {
            "captured_profile_count": len(profiles),
            "automatic_bucket_by_reference_branch": bucket_counts,
            "manually_confirmed_count": 0,
            "labels_created": 0,
        },
        "output": {"path": str(args.output), "sha256": sha256_file(args.output)},
        "gates": {
            "language_strata_open": False,
            "first_evidence_review_allowed": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
