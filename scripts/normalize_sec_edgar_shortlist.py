"""Independently review and normalize the SEC EDGAR/IAPD shortlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_sec_edgar_iapd_crosswalk import tokens


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left | right else 0.0


def write_jsonl(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument("--submissions-directory", type=Path, required=True)
    parser.add_argument("--iapd-normalized", type=Path, required=True)
    parser.add_argument("--opened-exclusion-index", type=Path, required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--edgar-output", type=Path, required=True)
    parser.add_argument("--iapd-disjoint-output", type=Path, required=True)
    parser.add_argument("--independent-review-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for output in (
        args.edgar_output,
        args.iapd_disjoint_output,
        args.independent_review_output,
        args.report,
    ):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    shortlist = load_jsonl(args.shortlist)
    iapd_rows = load_jsonl(args.iapd_normalized)
    exclusion = json.loads(args.opened_exclusion_index.read_text(encoding="utf-8"))
    opened_host_hashes = {
        record["normalized_host_sha256"]
        for record in exclusion.get("records", [])
        if record.get("normalized_host_sha256")
    }
    iapd_index = {
        (str(row["source_record_id"]), row["normalized_host"]): row for row in iapd_rows
    }
    decisions: list[dict] = []
    approved_rows: list[dict] = []
    for row in shortlist:
        cik = str(row["cik"])
        submission_path = args.submissions_directory / f"CIK{cik}.json"
        reasons: list[str] = []
        if not submission_path.is_file():
            reasons.append("SUBMISSION_FILE_MISSING")
            submission: dict = {}
        else:
            submission = json.loads(submission_path.read_text(encoding="utf-8"))
        submission_cik = str(submission.get("cik", "")).zfill(10)
        if submission_cik != cik:
            reasons.append("SUBMISSION_CIK_MISMATCH")
        submission_name = str(submission.get("name", ""))
        if not submission_name:
            reasons.append("SUBMISSION_NAME_MISSING")
        edgar_name_score = jaccard(tokens(submission_name), tokens(row["edgar_entity_name"]))
        iapd_name_score = jaccard(tokens(submission_name), tokens(row["iapd_entity_name"]))
        if edgar_name_score < 0.8:
            reasons.append("SUBMISSION_EDGAR_NAME_MISMATCH")
        if iapd_name_score < 0.8:
            reasons.append("SUBMISSION_IAPD_NAME_MISMATCH")
        iapd_key = (str(row["iapd_source_record_id"]), row["normalized_host"])
        iapd = iapd_index.get(iapd_key)
        if iapd is None:
            reasons.append("IAPD_HOST_OR_RECORD_MISMATCH")
        host_hash = hashlib.sha256(row["normalized_host"].encode("utf-8")).hexdigest()
        if host_hash in opened_host_hashes:
            reasons.append("OPENED_HOST_OVERLAP")
        decision = "APPROVE" if not reasons else "REJECT"
        decisions.append(
            {
                "cik": cik,
                "iapd_source_record_id": row["iapd_source_record_id"],
                "normalized_host_sha256": host_hash,
                "submission_sha256": sha256_file(submission_path) if submission_path.is_file() else None,
                "submission_edgar_name_jaccard": round(edgar_name_score, 6),
                "submission_iapd_name_jaccard": round(iapd_name_score, 6),
                "decision": decision,
                "reason_codes": reasons,
                "review_basis": "Independent exact CIK, frozen submission name, IAPD record/host, and opened-host exclusion checks.",
                "model_output_used": False,
                "candidate_domain_accessed": False,
                "ground_truth_label_created": False,
            }
        )
        if decision == "APPROVE":
            approved_rows.append(
                {
                    "source_id": "sec_edgar_company_submissions",
                    "source_record_id": cik,
                    "reference_url": f"https://data.sec.gov/submissions/CIK{cik}.json",
                    "reference_observed_at": args.observed_at,
                    "reference_sha256": sha256_file(submission_path),
                    "entity_name_from_reference": submission_name,
                    "candidate_url": row["candidate_url"],
                    "normalized_host": row["normalized_host"],
                    "identity_linkage_basis": (
                        "Exact SEC submission CIK plus independently reviewed high-overlap entity-name "
                        "match to the frozen IAPD record carrying this exact host."
                    ),
                    "opened_normalized_host": "PASS",
                    "opened_reference_identity": "PASS",
                    "legacy_component": "PASS",
                }
            )
    if len(approved_rows) < 10:
        raise ValueError(f"Fewer than 10 EDGAR rows passed independent review: {len(approved_rows)}")
    approved_hosts = {row["normalized_host"] for row in approved_rows}
    iapd_disjoint = [row for row in iapd_rows if row["normalized_host"] not in approved_hosts]
    if len(iapd_rows) - len(iapd_disjoint) != len(approved_hosts):
        raise ValueError("IAPD disjoint-pool removal count does not match approved EDGAR hosts")
    write_jsonl(args.edgar_output, approved_rows)
    write_jsonl(args.iapd_disjoint_output, iapd_disjoint)
    review = {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_SEC_EDGAR_INDEPENDENT_PROVENANCE_REVIEW_V1",
        "status": "COMPLETE_PROVENANCE_ONLY_NO_LABELS",
        "shortlist": {"path": str(args.shortlist), "sha256": sha256_file(args.shortlist)},
        "decision_counts": {
            "APPROVE": sum(item["decision"] == "APPROVE" for item in decisions),
            "REJECT": sum(item["decision"] == "REJECT" for item in decisions),
        },
        "records": decisions,
        "safety_contract": {
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    args.independent_review_output.parent.mkdir(parents=True, exist_ok=True)
    args.independent_review_output.write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = {
        "analysis_id": "ISI_TARGET_TEXT_CORPUS_V1_SEC_EDGAR_REFERENCE_NORMALIZATION_V1",
        "status": "FROZEN_INDEPENDENTLY_REVIEWED_REFERENCE_POOL_UNLABELED",
        "input_counts": {
            "shortlist": len(shortlist),
            "submission_files": len(list(args.submissions_directory.glob("CIK*.json"))),
            "iapd_rows": len(iapd_rows),
        },
        "review_counts": review["decision_counts"],
        "outputs": {
            "edgar_normalized": {
                "path": str(args.edgar_output),
                "sha256": sha256_file(args.edgar_output),
                "record_count": len(approved_rows),
                "unique_host_count": len(approved_hosts),
            },
            "iapd_disjoint": {
                "path": str(args.iapd_disjoint_output),
                "sha256": sha256_file(args.iapd_disjoint_output),
                "record_count": len(iapd_disjoint),
            },
            "independent_review": {
                "path": str(args.independent_review_output),
                "sha256": sha256_file(args.independent_review_output),
            },
        },
        "quality": {
            "cross_channel_host_overlap_after_separation": 0,
            "opened_host_overlap": 0,
            "approved_rows_are_labels": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "candidate_domain_access_operations": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
