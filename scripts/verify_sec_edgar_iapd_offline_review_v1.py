"""Independently verify SEC shortlist evidence extraction and offline review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_crosswalk import tokens as distinctive_tokens
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.normalization.external_references import canonicalize_host


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def independent_core(value: Any) -> list[str]:
    text = str(value).casefold()
    text = re.sub(r"\bl\W*l\W*c\b", " llc ", text)
    text = re.sub(r"\bl\W*p\b", " lp ", text)
    substitutions = {"corporation": "corp", "incorporated": "inc", "limited": "ltd"}
    legal = {"co", "corp", "inc", "llc", "llp", "lp", "ltd", "plc", "sa"}
    parts = [substitutions.get(token, token) for token in re.findall(r"[a-z0-9]+", text)]
    if parts and parts[0] == "the":
        parts = parts[1:]
    return [part for part in parts if part not in legal]


def independent_classification(edgar: str, iapd: str, threshold: float) -> tuple[str, str, float, float]:
    left = independent_core(edgar)
    right = independent_core(iapd)
    union = set(left) | set(right)
    full = len(set(left) & set(right)) / len(union) if union else 0.0
    distinct_left = distinctive_tokens(edgar)
    distinct_right = distinctive_tokens(iapd)
    distinct_union = distinct_left | distinct_right
    distinct = len(distinct_left & distinct_right) / len(distinct_union) if distinct_union else 0.0
    if left == right:
        return "OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS", "ADVANCE_TO_CAPTURE_PLANNING_REVIEW", round(full, 6), round(distinct, 6)
    if full >= threshold and distinct >= 0.8:
        return "OFFLINE_COMPATIBLE_NAME_VARIANT_EVIDENCE_PASS", "ADVANCE_TO_CAPTURE_PLANNING_REVIEW", round(full, 6), round(distinct, 6)
    return "OFFLINE_AMBIGUOUS_RELATED_NAME_CAUTION", "HOLD_FOR_DEEPER_IDENTITY_REVIEW", round(full, 6), round(distinct, 6)


def verify(config_path: Path, output_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_OFFLINE_REVIEW_V1":
        raise ValueError("Unexpected offline review protocol")
    root = config_path.resolve().parents[1]
    for item in config["basis"]:
        if sha256_file(root / item["path"]) != item["sha256"]:
            raise ValueError(f"Independent offline review basis mismatch: {item['role']}")
    for item in config["inputs"].values():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("Independent offline review input mismatch")
    for gate in ("candidate_live_domain_access_allowed", "wayback_query_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if config["decision"].get(gate) is not False:
            raise PermissionError(f"Independent verification found open gate: {gate}")

    output_dir = Path(config["outputs"]["directory"])
    evidence_dir = output_dir / config["outputs"]["evidence_subdirectory"]
    review_path = output_dir / config["outputs"]["review_records_filename"]
    report_path = output_dir / config["outputs"]["report_filename"]
    shortlist = jsonl(Path(config["inputs"]["shortlist"]["path"]))
    iapd_rows = jsonl(Path(config["inputs"]["iapd_normalized"]["path"]))
    review_rows = jsonl(review_path)
    report = load_object(report_path)
    if len(shortlist) != config["inputs"]["shortlist"]["record_count"] or len(review_rows) != len(shortlist):
        raise ValueError("Independent offline review coverage mismatch")
    if [row["shortlist_id"] for row in review_rows] != [row["shortlist_id"] for row in shortlist]:
        raise ValueError("Independent offline review order mismatch")
    shortlist_by_id = {row["shortlist_id"]: row for row in shortlist}
    iapd_by_id = {str(row["source_record_id"]): row for row in iapd_rows}
    expected_members = {f"CIK{row['cik']}.json" for row in shortlist}
    actual_members = {path.name for path in evidence_dir.iterdir() if path.is_file()}
    if actual_members != expected_members:
        raise ValueError("Independent extracted evidence member-set mismatch")

    threshold = float(config["review_contract"]["compatible_full_token_jaccard_minimum"])
    identity_counts: Counter[str] = Counter()
    recommendation_counts: Counter[str] = Counter()
    fingerprint_lines: list[str] = []
    total_bytes = 0
    archive_path = Path(config["inputs"]["raw_archive"]["path"])
    with zipfile.ZipFile(archive_path) as archive:
        for review in review_rows:
            shortlist_row = shortlist_by_id[review["shortlist_id"]]
            member_name = f"CIK{shortlist_row['cik']}.json"
            info = archive.getinfo(member_name)
            archived_bytes = archive.read(info)
            extracted_path = evidence_dir / member_name
            extracted_bytes = extracted_path.read_bytes()
            if extracted_bytes != archived_bytes:
                raise ValueError("Independent byte-preservation check failed")
            digest = hashlib.sha256(archived_bytes).hexdigest()
            submission = json.loads(archived_bytes)
            if str(submission.get("cik", "")).zfill(10) != shortlist_row["cik"] or submission.get("name") != shortlist_row["edgar_entity_name"]:
                raise ValueError("Independent SEC provenance check failed")
            iapd = iapd_by_id.get(str(shortlist_row["iapd_source_record_id"]))
            if iapd is None or iapd["entity_name_from_reference"] != shortlist_row["iapd_entity_name"]:
                raise ValueError("Independent IAPD identity check failed")
            host = canonicalize_host(iapd["normalized_host"])
            if not host or host != canonicalize_host(iapd["candidate_url"]) or host != shortlist_row["normalized_host"]:
                raise ValueError("Independent IAPD host provenance check failed")
            if hashlib.sha256(host.encode()).hexdigest() != shortlist_row["normalized_host_sha256"]:
                raise ValueError("Independent IAPD host-hash check failed")
            status, recommendation, full, distinct = independent_classification(submission["name"], iapd["entity_name_from_reference"], threshold)
            expected = {
                "sec_zip_member": member_name,
                "sec_zip_member_crc32": f"{info.CRC:08x}",
                "sec_zip_member_uncompressed_bytes": len(archived_bytes),
                "sec_submission_sha256": digest,
                "sec_provenance_status": "OFFLINE_ARCHIVE_MEMBER_CIK_AND_NAME_VERIFIED",
                "identity_review_status": status,
                "future_capture_planning_recommendation": recommendation,
                "full_token_jaccard": full,
                "distinctive_token_jaccard": distinct,
                "ground_truth_status": "UNCERTAIN",
                "training_eligible": "NO",
            }
            if any(review.get(key) != value for key, value in expected.items()):
                raise ValueError("Independent review-row reproduction failed")
            for field in ("candidate_live_domain_accessed", "wayback_queried", "artifact_captured", "label_created"):
                if review.get(field) is not False:
                    raise ValueError("Independent review safety-state check failed")
            identity_counts[status] += 1
            recommendation_counts[recommendation] += 1
            total_bytes += len(archived_bytes)
            fingerprint_lines.append(f"{member_name}|{digest}|{len(archived_bytes)}")

    fingerprint = hashlib.sha256("\n".join(sorted(fingerprint_lines)).encode()).hexdigest()
    if report["output"]["review_records_sha256"] != sha256_file(review_path):
        raise ValueError("Independent review report hash mismatch")
    if report["output"]["evidence_record_count"] != len(review_rows) or report["output"]["evidence_total_uncompressed_bytes"] != total_bytes or report["output"]["evidence_set_fingerprint"] != fingerprint:
        raise ValueError("Independent evidence report mismatch")
    if report["review"]["identity_status_counts"] != dict(sorted(identity_counts.items())) or report["review"]["future_capture_planning_recommendation_counts"] != dict(sorted(recommendation_counts.items())):
        raise ValueError("Independent review-count reproduction failed")

    result = {
        "verification_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_OFFLINE_REVIEW_INDEPENDENT_VERIFICATION_V1",
        "status": "PASS",
        "config_sha256": sha256_file(config_path),
        "review_records_sha256": sha256_file(review_path),
        "report_sha256": sha256_file(report_path),
        "checks": {
            "shortlist_coverage": len(review_rows),
            "exact_extracted_member_set": True,
            "raw_member_bytes_match_archive": True,
            "sec_cik_and_name_provenance_verified": True,
            "iapd_record_host_and_url_provenance_verified": True,
            "identity_classifications_independently_reproduced": True,
            "identity_status_counts": dict(sorted(identity_counts.items())),
            "recommendation_counts": dict(sorted(recommendation_counts.items())),
            "ground_truth_labels_created": 0,
        },
        "operations": {"network": 0, "candidate_domain_access": 0, "wayback_queries": 0, "captures": 0, "labels": 0, "model": 0},
    }
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite independent offline review verification")
    temporary = output_path.with_suffix(output_path.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.config, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
