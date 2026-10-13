"""Materialize bounded SEC shortlist evidence and review its provenance offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_crosswalk import tokens as distinctive_tokens
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.normalization.external_references import canonicalize_host


LEGAL_NORMALIZATION = {
    "corporation": "corp",
    "incorporated": "inc",
    "limited": "ltd",
}
LEGAL_SUFFIXES = {"co", "corp", "inc", "llc", "llp", "lp", "ltd", "plc", "sa"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized_name_tokens(value: Any) -> list[str]:
    raw = re.findall(r"[a-z0-9]+", str(value).casefold())
    collapsed: list[str] = []
    index = 0
    while index < len(raw):
        if raw[index : index + 3] == ["l", "l", "c"]:
            collapsed.append("llc")
            index += 3
        elif raw[index : index + 2] in (["l", "p"], ["l", "l"]):
            collapsed.append("lp" if raw[index + 1] == "p" else "ll")
            index += 2
        else:
            collapsed.append(LEGAL_NORMALIZATION.get(raw[index], raw[index]))
            index += 1
    if collapsed and collapsed[0] == "the":
        collapsed = collapsed[1:]
    return collapsed


def core_name_tokens(value: Any) -> list[str]:
    return [token for token in normalized_name_tokens(value) if token not in LEGAL_SUFFIXES]


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left | right else 0.0


def classify_name_evidence(edgar_name: str, iapd_name: str, threshold: float) -> dict[str, Any]:
    edgar_core = core_name_tokens(edgar_name)
    iapd_core = core_name_tokens(iapd_name)
    full_score = jaccard(set(edgar_core), set(iapd_core))
    distinctive_score = jaccard(distinctive_tokens(edgar_name), distinctive_tokens(iapd_name))
    if edgar_core == iapd_core:
        status = "OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS"
        recommendation = "ADVANCE_TO_CAPTURE_PLANNING_REVIEW"
    elif full_score >= threshold and distinctive_score >= 0.8:
        status = "OFFLINE_COMPATIBLE_NAME_VARIANT_EVIDENCE_PASS"
        recommendation = "ADVANCE_TO_CAPTURE_PLANNING_REVIEW"
    else:
        status = "OFFLINE_AMBIGUOUS_RELATED_NAME_CAUTION"
        recommendation = "HOLD_FOR_DEEPER_IDENTITY_REVIEW"
    return {
        "identity_review_status": status,
        "future_capture_planning_recommendation": recommendation,
        "edgar_core_name_tokens": edgar_core,
        "iapd_core_name_tokens": iapd_core,
        "full_token_jaccard": round(full_score, 6),
        "distinctive_token_jaccard": round(distinctive_score, 6),
    }


def validate_config(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != "ISI_SEC_EDGAR_IAPD_ALL_FILER_OFFLINE_REVIEW_V1":
        raise ValueError("Unexpected SEC EDGAR/IAPD offline review protocol")
    root = config_path.resolve().parents[1]
    for item in config["basis"]:
        path = root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Offline review basis mismatch: {item['role']}")
    for item in config["inputs"].values():
        path = Path(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError("Offline review input hash mismatch")
    decision = config["decision"]
    if decision.get("shortlist_only_evidence_extraction_allowed") is not True or decision.get("offline_provenance_review_allowed") is not True:
        raise PermissionError("Offline shortlist evidence review is not authorized")
    for gate in ("candidate_live_domain_access_allowed", "wayback_query_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(gate) is not False:
            raise PermissionError(f"Offline review opened forbidden gate: {gate}")
    return config


def remove_staging(staging: Path, output: Path) -> None:
    if not staging.exists():
        return
    if staging.resolve().parent != output.resolve().parent or staging.name != output.name + ".partial":
        raise RuntimeError("Refusing to remove unexpected offline review staging directory")
    shutil.rmtree(staging)


def materialize(config_path: Path) -> dict[str, Any]:
    config = validate_config(config_path)
    output = Path(config["outputs"]["directory"])
    staging = output.with_name(output.name + ".partial")
    if output.exists() or staging.exists():
        raise FileExistsError("Refusing to overwrite SEC offline review output")
    staging.mkdir(parents=True)
    evidence_dir = staging / config["outputs"]["evidence_subdirectory"]
    evidence_dir.mkdir()
    try:
        shortlist = load_jsonl(Path(config["inputs"]["shortlist"]["path"]))
        if len(shortlist) != config["inputs"]["shortlist"]["record_count"]:
            raise ValueError("Offline review shortlist count mismatch")
        if len({row["cik"] for row in shortlist}) != len(shortlist):
            raise ValueError("Offline review shortlist CIKs are not unique")
        iapd_rows = load_jsonl(Path(config["inputs"]["iapd_normalized"]["path"]))
        if len(iapd_rows) != config["inputs"]["iapd_normalized"]["record_count"]:
            raise ValueError("Offline review IAPD count mismatch")
        iapd_by_id = {str(row["source_record_id"]): row for row in iapd_rows}
        archive_path = Path(config["inputs"]["raw_archive"]["path"])
        threshold = float(config["review_contract"]["compatible_full_token_jaccard_minimum"])
        reviews: list[dict[str, Any]] = []
        total_bytes = 0
        with zipfile.ZipFile(archive_path) as archive:
            member_names = set(archive.namelist())
            for shortlist_row in shortlist:
                cik = str(shortlist_row["cik"])
                member_name = f"CIK{cik}.json"
                if member_name not in member_names:
                    raise ValueError(f"Shortlisted SEC member missing: {member_name}")
                info = archive.getinfo(member_name)
                raw = archive.read(info)
                submission = json.loads(raw)
                submission_cik = str(submission.get("cik", "")).strip().zfill(10)
                submission_name = str(submission.get("name", "")).strip()
                if submission_cik != cik:
                    raise ValueError("SEC member filename/JSON/shortlist CIK mismatch")
                if submission_name != shortlist_row["edgar_entity_name"]:
                    raise ValueError("SEC member name differs from frozen shortlist")
                iapd = iapd_by_id.get(str(shortlist_row["iapd_source_record_id"]))
                if iapd is None or iapd["entity_name_from_reference"] != shortlist_row["iapd_entity_name"]:
                    raise ValueError("IAPD record identity differs from frozen shortlist")
                host = canonicalize_host(str(iapd.get("normalized_host", "")))
                url_host = canonicalize_host(str(iapd.get("candidate_url", "")))
                if not host or host != url_host or host != shortlist_row["normalized_host"]:
                    raise ValueError("IAPD host or URL differs from frozen shortlist")
                host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
                if host_hash != shortlist_row["normalized_host_sha256"]:
                    raise ValueError("IAPD host hash differs from frozen shortlist")
                for field in ("candidate_live_domain_accessed", "wayback_queried", "artifact_captured", "label_created"):
                    if shortlist_row[field] is not False:
                        raise ValueError("Shortlist safety state changed before offline review")
                if shortlist_row["ground_truth_status"] != "UNCERTAIN" or shortlist_row["training_eligible"] != "NO":
                    raise ValueError("Shortlist ground-truth or training gate changed")
                target = evidence_dir / member_name
                with target.open("xb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                member_sha = hashlib.sha256(raw).hexdigest()
                if sha256_file(target) != member_sha:
                    raise ValueError("Extracted SEC evidence hash mismatch")
                total_bytes += len(raw)
                name_review = classify_name_evidence(submission_name, iapd["entity_name_from_reference"], threshold)
                reviews.append(
                    {
                        "shortlist_id": shortlist_row["shortlist_id"],
                        "cohort": shortlist_row["cohort"],
                        "cik": cik,
                        "iapd_source_record_id": str(shortlist_row["iapd_source_record_id"]),
                        "normalized_host_sha256": host_hash,
                        "sec_zip_member": member_name,
                        "sec_zip_member_crc32": f"{info.CRC:08x}",
                        "sec_zip_member_uncompressed_bytes": info.file_size,
                        "sec_submission_sha256": member_sha,
                        "sec_submission_name": submission_name,
                        "iapd_entity_name": iapd["entity_name_from_reference"],
                        "sec_provenance_status": "OFFLINE_ARCHIVE_MEMBER_CIK_AND_NAME_VERIFIED",
                        **name_review,
                        "ground_truth_status": "UNCERTAIN",
                        "candidate_live_domain_accessed": False,
                        "wayback_queried": False,
                        "artifact_captured": False,
                        "label_created": False,
                        "training_eligible": "NO",
                    }
                )
        status_counts = Counter(row["identity_review_status"] for row in reviews)
        recommendation_counts = Counter(row["future_capture_planning_recommendation"] for row in reviews)
        review_path = staging / config["outputs"]["review_records_filename"]
        review_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in reviews), encoding="utf-8")
        evidence_manifest = sorted(
            f"{row['sec_zip_member']}|{row['sec_submission_sha256']}|{row['sec_zip_member_uncompressed_bytes']}" for row in reviews
        )
        report = {
            "analysis_id": "ISI_SEC_EDGAR_IAPD_ALL_FILER_OFFLINE_REVIEW_V1",
            "status": "COMPLETE_OFFLINE_PROVENANCE_AND_CONSERVATIVE_IDENTITY_REVIEW_NO_LABELS",
            "input": {
                "raw_archive_sha256": config["inputs"]["raw_archive"]["sha256"],
                "shortlist_sha256": config["inputs"]["shortlist"]["sha256"],
                "iapd_normalized_sha256": config["inputs"]["iapd_normalized"]["sha256"],
            },
            "output": {
                "evidence_record_count": len(reviews),
                "evidence_total_uncompressed_bytes": total_bytes,
                "evidence_set_fingerprint": hashlib.sha256("\n".join(evidence_manifest).encode("utf-8")).hexdigest(),
                "review_records_filename": review_path.name,
                "review_records_sha256": sha256_file(review_path),
            },
            "review": {
                "development_rows": sum(row["cohort"] == "DEVELOPMENT" for row in reviews),
                "external_holdout_rows": sum(row["cohort"] == "EXTERNAL_HOLDOUT" for row in reviews),
                "provenance_verified_rows": len(reviews),
                "identity_status_counts": dict(sorted(status_counts.items())),
                "future_capture_planning_recommendation_counts": dict(sorted(recommendation_counts.items())),
                "ground_truth_labels_created": 0,
            },
            "decision": {
                "offline_provenance_review_passed": len(reviews) == config["inputs"]["shortlist"]["record_count"],
                "advance_recommendations_are_capture_authorization": False,
                "caution_rows_require_deeper_identity_review": True,
                "candidate_live_domain_access_allowed": False,
                "wayback_query_allowed": False,
                "artifact_capture_allowed": False,
                "labeling_allowed": False,
                "training_allowed": False,
            },
            "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "wayback_queries": 0, "artifact_captures": 0, "labels_created": 0, "model_operations": 0},
        }
        report_path = staging / config["outputs"]["report_filename"]
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.replace(output)
        report["output_directory"] = str(output)
        return report
    except Exception:
        remove_staging(staging, output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
