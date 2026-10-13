"""Acquire the official SEC submissions.zip once after an explicit release gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
    verify,
)


REQUIRED_PRIVATE_FIELDS = ("organization_or_project", "contact_email", "purpose")
EXPECTED_BULK_HOST = "www.sec.gov"
EXPECTED_RELEASE_IDS = {
    "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1_EXECUTION_RELEASE",
    "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1_EXECUTION_RELEASE_V2",
}


def validate_private_identity(path: Path) -> str:
    identity = load_object(path)
    if set(identity) != set(REQUIRED_PRIVATE_FIELDS):
        raise ValueError("Private SEC identity field contract changed")
    values = {key: str(identity[key]).strip() for key in REQUIRED_PRIVATE_FIELDS}
    if any(not value for value in values.values()):
        raise ValueError("Private SEC identity fields must be non-empty")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["contact_email"]):
        raise ValueError("Private SEC contact email is invalid")
    if "investment" not in values["purpose"].casefold() or "research" not in values["purpose"].casefold():
        raise ValueError("Private SEC purpose must identify investment research")
    return f"{values['organization_or_project']} {values['contact_email']}"


def validate_execution_release(
    release_path: Path,
    protocol_path: Path,
    tooling_registry_path: Path,
    output: Path,
    manifest: Path,
) -> dict[str, Any]:
    release = load_object(release_path)
    if release.get("release_id") not in EXPECTED_RELEASE_IDS:
        raise PermissionError("SEC bulk execution release identity is invalid")
    if release.get("status") != "FROZEN_ONE_SHOT_NETWORK_EXECUTION_RELEASED":
        raise PermissionError("SEC bulk execution release is not active")

    basis = {item["role"]: item for item in release.get("basis", [])}
    required = {
        "source_capacity_amendment_protocol": protocol_path,
        "sec_bulk_tooling_registry": tooling_registry_path,
    }
    if release.get("release_id", "").endswith("_V2"):
        if release.get("release_sequence") != 2:
            raise PermissionError("SEC bulk retry release sequence is invalid")
        prior = basis.get("prior_failed_acquisition_attempt")
        if not prior:
            raise PermissionError("SEC bulk retry release lacks prior-attempt evidence")
        prior_path = Path(prior["path"])
        if not prior_path.is_absolute():
            prior_path = release_path.resolve().parents[1] / prior_path
        if not prior_path.is_file() or sha256_file(prior_path) != prior["sha256"]:
            raise PermissionError("SEC bulk retry release prior-attempt evidence mismatch")
    for role, expected_path in required.items():
        item = basis.get(role)
        if not item:
            raise PermissionError(f"SEC bulk execution release lacks {role}")
        registered_path = Path(item["path"])
        if not registered_path.is_absolute():
            registered_path = release_path.resolve().parents[1] / registered_path
        if registered_path.resolve() != expected_path.resolve():
            raise PermissionError(f"SEC bulk execution release path mismatch for {role}")
        if sha256_file(expected_path) != item["sha256"]:
            raise PermissionError(f"SEC bulk execution release hash mismatch for {role}")

    scope = release.get("execution_scope", {})
    protocol = load_object(protocol_path)
    if scope.get("source_url") != protocol["sec_edgar_bulk"]["official_bulk_url"]:
        raise PermissionError("SEC bulk execution release URL differs from protocol")
    if scope.get("maximum_requests") != 1:
        raise PermissionError("SEC bulk execution release must allow exactly one request")
    if Path(scope.get("raw_output", "")) != output:
        raise PermissionError("SEC bulk execution release output path mismatch")
    if Path(scope.get("manifest_output", "")) != manifest:
        raise PermissionError("SEC bulk execution release manifest path mismatch")

    identity_evidence = release.get("private_identity_evidence", {})
    if identity_evidence != {
        "file_exists_at_release": True,
        "required_fields_validated_at_release": True,
        "contents_disclosed": False,
        "hash_disclosed": False,
        "runtime_revalidation_required": True,
    }:
        raise PermissionError("SEC bulk private-identity evidence contract changed")

    decision = release.get("decision", {})
    required_decision = {
        "sec_bulk_network_execution_allowed": True,
        "candidate_enumeration_allowed": False,
        "capture_allowed": False,
        "labeling_allowed": False,
        "training_allowed": False,
        "model_scoring_allowed": False,
        "validation_or_test_opening_allowed": False,
    }
    if any(decision.get(key) is not value for key, value in required_decision.items()):
        raise PermissionError("SEC bulk execution release decision contract changed")
    return release


def safe_zip_summary(path: Path, *, full_crc_check: bool) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos:
            raise ValueError("SEC bulk ZIP is empty")
        names: set[str] = set()
        json_members = 0
        non_json_members = 0
        extension_counts: dict[str, int] = {}
        uncompressed_bytes = 0
        compressed_bytes = 0
        for info in infos:
            normalized = info.filename.replace("\\", "/")
            member = PurePosixPath(normalized)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError("SEC bulk ZIP contains an unsafe member path")
            if normalized in names:
                raise ValueError("SEC bulk ZIP contains a duplicate member name")
            names.add(normalized)
            if info.flag_bits & 0x1:
                raise ValueError("SEC bulk ZIP contains an encrypted member")
            if not info.is_dir():
                extension = member.suffix.casefold() or "<none>"
                extension_counts[extension] = extension_counts.get(extension, 0) + 1
                if extension == ".json":
                    json_members += 1
                else:
                    non_json_members += 1
            uncompressed_bytes += info.file_size
            compressed_bytes += info.compress_size
        if json_members == 0:
            raise ValueError("SEC bulk ZIP contains no JSON members")
        if full_crc_check:
            failing = archive.testzip()
            if failing is not None:
                raise ValueError("SEC bulk ZIP failed CRC validation")
    return {
        "member_count": len(infos),
        "json_member_count": json_members,
        "non_json_member_count": non_json_members,
        "file_extension_counts": dict(sorted(extension_counts.items())),
        "uncompressed_bytes": uncompressed_bytes,
        "compressed_bytes": compressed_bytes,
    }


def stream_response(response: BinaryIO, output: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    with output.open("xb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            total += len(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    return total, digest.hexdigest()


def public_manifest(
    *,
    protocol_path: Path,
    release_path: Path,
    source_url: str,
    output_path: Path,
    collected_at: str,
    status_code: int,
    content_type: str,
    bytes_written: int,
    archive_sha256: str,
    zip_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "manifest_id": "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1",
        "status": "FROZEN_OFFICIAL_BULK_ARCHIVE_ACQUIRED_NO_CANDIDATES",
        "source_id": "sec_edgar_company_submissions",
        "source_url": source_url,
        "collected_at": collected_at,
        "acquisition_mode": "ONE_SHOT_OFFICIAL_BULK_ARCHIVE",
        "protocol": {"path": str(protocol_path), "sha256": sha256_file(protocol_path)},
        "execution_release": {"path": str(release_path), "sha256": sha256_file(release_path)},
        "transport": {
            "http_status": status_code,
            "content_type": content_type,
            "request_count": 1,
            "private_identity_runtime_validated": True,
            "private_identity_disclosed": False,
            "private_identity_hash_disclosed": False,
        },
        "raw_artifact": {
            "path": str(output_path),
            "bytes": bytes_written,
            "sha256": archive_sha256,
            **zip_summary,
        },
        "interpretation": {
            "public_filing_history_reference_only": True,
            "automatic_legitimate_label": False,
            "candidate_enumeration_allowed": False,
            "independent_identity_review_required": True,
        },
        "safety_contract": {
            "candidate_domain_access_operations": 0,
            "candidate_records_enumerated": 0,
            "artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }


def acquire(
    protocol_path: Path,
    release_path: Path,
    tooling_registry_path: Path,
    private_identity_path: Path,
    output: Path,
    manifest: Path,
) -> dict[str, Any]:
    verification = verify(protocol_path)
    protocol = load_object(protocol_path)
    if verification["sec_bulk_network_execution_allowed_now"] is not False:
        raise PermissionError("Frozen protocol baseline unexpectedly changed")
    if output.exists() or manifest.exists():
        raise FileExistsError("Refusing to overwrite frozen SEC bulk output or manifest")
    if output != Path(protocol["sec_edgar_bulk"]["planned_raw_output"]):
        raise ValueError("SEC bulk output path differs from the frozen protocol")
    if manifest != output.with_suffix(".manifest.json"):
        raise ValueError("SEC bulk manifest path must be derived from the frozen raw path")

    validate_execution_release(
        release_path,
        protocol_path,
        tooling_registry_path,
        output,
        manifest,
    )

    user_agent = validate_private_identity(private_identity_path)
    source_url = protocol["sec_edgar_bulk"]["official_bulk_url"]
    request = urllib.request.Request(
        source_url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "identity",
            "Host": EXPECTED_BULK_HOST,
        },
        method="GET",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    if partial.exists():
        raise FileExistsError(f"Refusing to overwrite partial SEC bulk file: {partial}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status == 429:
                raise RuntimeError("SEC returned HTTP 429; stop immediately")
            if status != 200:
                raise RuntimeError(f"SEC bulk request failed with HTTP {status}")
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip()
            bytes_written, archive_hash = stream_response(response, partial)
        summary = safe_zip_summary(partial, full_crc_check=True)
        partial.replace(output)
        result = public_manifest(
            protocol_path=protocol_path,
            release_path=release_path,
            source_url=source_url,
            output_path=output,
            collected_at=datetime.now(timezone.utc).isoformat(),
            status_code=status,
            content_type=content_type,
            bytes_written=bytes_written,
            archive_sha256=archive_hash,
            zip_summary=summary,
        )
        with manifest.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return result
    except Exception:
        if partial.exists():
            partial.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--tooling-registry", type=Path, required=True)
    parser.add_argument("--private-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = acquire(
        args.protocol,
        args.release,
        args.tooling_registry,
        args.private_identity,
        args.output,
        args.manifest,
    )
    print(
        json.dumps(
            {
                "manifest_id": result["manifest_id"],
                "raw_artifact": result["raw_artifact"],
                "private_identity_disclosed": False,
                "candidate_records_enumerated": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
