"""Independently verify the acquired SEC submissions bulk archive and manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.acquire_sec_edgar_submissions_bulk_v1 import safe_zip_summary
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


EXPECTED_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
SUMMARY_KEYS = (
    "member_count",
    "json_member_count",
    "non_json_member_count",
    "file_extension_counts",
    "uncompressed_bytes",
    "compressed_bytes",
)


def resolve_registered_path(repository_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repository_root / path


def verify(manifest_path: Path, repository_root: Path, *, full_crc_check: bool = True) -> dict[str, Any]:
    manifest = load_object(manifest_path)
    if manifest.get("manifest_id") != "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1":
        raise ValueError("Unexpected SEC bulk manifest identity")
    if manifest.get("status") != "FROZEN_OFFICIAL_BULK_ARCHIVE_ACQUIRED_NO_CANDIDATES":
        raise ValueError("SEC bulk acquisition is not frozen as acquired")
    if manifest.get("source_url") != EXPECTED_URL:
        raise ValueError("SEC bulk source URL changed")

    for key in ("protocol", "execution_release"):
        registration = manifest.get(key, {})
        path = resolve_registered_path(repository_root, registration.get("path", ""))
        if not path.is_file() or sha256_file(path) != registration.get("sha256"):
            raise ValueError(f"SEC bulk {key} hash binding failed")

    transport = manifest.get("transport", {})
    expected_transport = {
        "http_status": 200,
        "request_count": 1,
        "private_identity_runtime_validated": True,
        "private_identity_disclosed": False,
        "private_identity_hash_disclosed": False,
    }
    if any(transport.get(key) != value for key, value in expected_transport.items()):
        raise ValueError("SEC bulk transport or privacy contract changed")

    raw = manifest.get("raw_artifact", {})
    archive = Path(raw.get("path", ""))
    if not archive.is_file():
        raise FileNotFoundError("SEC bulk raw archive is missing")
    if archive.stat().st_size != raw.get("bytes"):
        raise ValueError("SEC bulk byte size differs from manifest")
    if sha256_file(archive) != raw.get("sha256"):
        raise ValueError("SEC bulk SHA-256 differs from manifest")
    observed_summary = safe_zip_summary(archive, full_crc_check=full_crc_check)
    if any(observed_summary[key] != raw.get(key) for key in SUMMARY_KEYS):
        raise ValueError("SEC bulk ZIP summary differs from manifest")

    interpretation = manifest.get("interpretation", {})
    if interpretation != {
        "public_filing_history_reference_only": True,
        "automatic_legitimate_label": False,
        "candidate_enumeration_allowed": False,
        "independent_identity_review_required": True,
    }:
        raise ValueError("SEC bulk interpretation contract changed")
    safety = manifest.get("safety_contract", {})
    if safety != {
        "candidate_domain_access_operations": 0,
        "candidate_records_enumerated": 0,
        "artifact_captures": 0,
        "labels_created": 0,
        "model_operations": 0,
        "training_allowed": False,
    }:
        raise ValueError("SEC bulk downstream safety contract changed")

    serialized = json.dumps(manifest, ensure_ascii=False).casefold()
    for forbidden in ("contact_email", "organization_or_project"):
        if forbidden in serialized:
            raise ValueError("Private SEC identity field leaked into public manifest")

    return {
        "status": "VERIFIED_IMMUTABLE_RAW_REFERENCE_ONLY",
        "manifest_sha256": sha256_file(manifest_path),
        "archive_sha256": raw["sha256"],
        "archive_bytes": raw["bytes"],
        **observed_summary,
        "candidate_records_enumerated": 0,
        "labels_created": 0,
        "training_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--skip-full-crc", action="store_true")
    args = parser.parse_args()
    result = verify(
        args.manifest,
        args.repository_root,
        full_crc_check=not args.skip_full_crc,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
