"""Extract exact visible text offline from verified V11 recovery captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_exact_text_release import EXPECTED_IDS, RELEASE_ID
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_exact_text_release import QA_ID
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file
from src.isi.normalization.external_text import extract_visible_text
from src.isi.normalization.wayback_external_text import decode_archived_payload


RELEASE_QA_STATUS = "PASS_V11_METADATA_RECOVERY_EXACT_TEXT_RELEASE"
REPORT_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_EXACT_TEXT_EXTRACTION_REPORT_V1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_component(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    if not result or result in {".", ".."}:
        raise ValueError(f"Unsafe record ID: {value}")
    return result


def prepare(release_path: Path, release_qa_path: Path) -> tuple[dict[str, Any], list[tuple[dict[str, Any], bytes]], dict[str, Path]]:
    release = load_object(release_path)
    release_qa = load_object(release_qa_path)
    if release.get("release_id") != RELEASE_ID:
        raise ValueError("Unexpected recovery exact-text release identity")
    if release_qa.get("verification_id") != QA_ID or release_qa.get("status") != RELEASE_QA_STATUS or release_qa.get("inputs", {}).get("release_sha256") != sha256_file(release_path):
        raise ValueError("Recovery exact-text release QA status or binding mismatch")
    if release_qa.get("decision", {}).get("offline_exact_text_extraction_allowed_after_release_qa") is not True:
        raise PermissionError("Recovery exact-text extraction gate is closed")
    capture_path = Path(str(release["inputs"]["capture_report"]["path"]))
    if sha256_file(capture_path) != release["inputs"]["capture_report"]["sha256"]:
        raise ValueError("Recovery capture report hash changed")
    capture = load_object(capture_path)
    rows = list(capture.get("results", []))
    if capture.get("status") != "COMPLETE" or [row.get("availability_plan_id") for row in rows] != list(EXPECTED_IDS) or any(row.get("outcome") != "CAPTURED" for row in rows):
        raise ValueError("Recovery capture report is not exact-two-row COMPLETE")
    minimum = release.get("method", {}).get("minimum_non_whitespace_text_characters")
    if minimum != 20:
        raise ValueError("Frozen minimum content threshold changed")
    outputs = {key: Path(str(release["outputs"][key])) for key in ("text_root", "manifest", "report")}
    prepared: list[tuple[dict[str, Any], bytes]] = []
    for capture_row in rows:
        record_id = str(capture_row["availability_plan_id"])
        raw_path = Path(str(capture_row["capture_path"]))
        raw = raw_path.read_bytes()
        if len(raw) != capture_row.get("bytes") or sha256_bytes(raw) != capture_row.get("sha256"):
            raise ValueError(f"Recovery raw byte/hash mismatch: {record_id}")
        decoded, transport = decode_archived_payload(raw)
        text, canonical_urls = extract_visible_text(decoded)
        text_bytes = text.encode("utf-8")
        non_whitespace = len(re.sub(r"\s+", "", text))
        text_path = outputs["text_root"] / f"{safe_component(record_id)}.txt"
        manifest = {
            "schema_version": "sec_edgar_iapd_v11_metadata_recovery_exact_text_v1",
            "record_id": record_id,
            "availability_plan_id": record_id,
            "shortlist_id": capture_row["shortlist_id"],
            "cohort": capture_row["cohort"],
            "candidate_host": capture_row["candidate_host"],
            "candidate_url": capture_row["candidate_url"],
            "snapshot_timestamp": capture_row["snapshot_timestamp"],
            "archive_url": capture_row["final_archive_url"],
            "raw_capture_path": str(raw_path),
            "raw_capture_bytes": len(raw),
            "raw_capture_sha256": sha256_bytes(raw),
            "transport_decoding": transport,
            "decoded_bytes": len(decoded),
            "decoded_sha256": sha256_bytes(decoded),
            "canonical_urls_declared_in_capture": canonical_urls,
            "text_path": str(text_path),
            "text_encoding": "UTF-8",
            "text_bytes": len(text_bytes),
            "text_sha256": sha256_bytes(text_bytes),
            "visible_text_characters": len(text),
            "non_whitespace_text_characters": non_whitespace,
            "minimum_non_whitespace_text_characters": minimum,
            "minimum_content_passed": non_whitespace >= minimum,
            "content_gate_state": "MINIMUM_CONTENT_PASS" if non_whitespace >= minimum else "BELOW_MINIMUM_PRESERVED",
            "ground_truth_status": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
            "model_scoring_eligible": "NO",
        }
        prepared.append((manifest, text_bytes))
    return release, prepared, outputs


def execute(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    release, prepared, outputs = prepare(release_path, release_qa_path)
    if any(path.exists() for path in outputs.values()):
        raise FileExistsError("Refusing to overwrite recovery exact-text outputs")
    outputs["text_root"].mkdir(parents=True, exist_ok=False)
    for row, text_bytes in prepared:
        text_path = Path(str(row["text_path"]))
        if text_path.parent.resolve() != outputs["text_root"].resolve():
            raise ValueError("Recovery text path escaped frozen output root")
        with text_path.open("xb") as handle:
            handle.write(text_bytes)
    outputs["manifest"].parent.mkdir(parents=True, exist_ok=True)
    with outputs["manifest"].open("x", encoding="utf-8", newline="\n") as handle:
        for row, _ in prepared:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    passed = sum(row["minimum_content_passed"] for row, _ in prepared)
    report = {
        "report_id": REPORT_ID,
        "created_at": release["created_at"],
        "status": "OFFLINE_EXTRACTION_COMPLETE_INDEPENDENT_QA_REQUIRED",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "release_qa": {"path": str(release_qa_path.resolve()), "sha256": sha256_file(release_qa_path)},
        "counts": {"extracted_count": len(prepared), "minimum_content_passed_count": passed, "below_minimum_preserved_count": len(prepared) - passed, "by_cohort": dict(Counter(row["cohort"] for row, _ in prepared)), "labels_created": 0},
        "outputs": {"text_root": str(outputs["text_root"]), "text_file_count": len(prepared), "manifest": {"path": str(outputs["manifest"]), "sha256": sha256_file(outputs["manifest"])}},
        "gates": {"independent_byte_for_byte_qa_required": True, "post_capture_grouping_required": True, "human_label_review_allowed": False, "model_scoring_allowed": False, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "raw_files_modified": 0, "labels_created": 0, "model_operations": 0},
    }
    with outputs["report"].open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    args = parser.parse_args()
    report = execute(args.release, args.release_qa)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
