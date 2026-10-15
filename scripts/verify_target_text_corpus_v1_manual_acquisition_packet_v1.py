"""Verify the frozen manual-acquisition handoff without touching source sites."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


EXPECTED_PACKET_ID = "ISI_TARGET_TEXT_CORPUS_V1_MANUAL_ACQUISITION_PACKET_V1"
EXPECTED_SOURCES = {
    "dfpi_crypto_scam_tracker",
    "ssc_vietnam_investor_warnings",
    "hnx_vietnam_issuer_profiles",
}
BLOCKED_VIETNAMESE_SOURCES = {
    "ssc_vietnam_investor_warnings",
    "hnx_vietnam_issuer_profiles",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _resolve_repo_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def verify(packet_path: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    if packet.get("packet_id") != EXPECTED_PACKET_ID:
        raise ValueError("Unexpected manual-acquisition packet ID")
    if packet.get("status") != "FROZEN_INSTRUCTIONS_ONLY_NO_SOURCE_ACTIVATED":
        raise ValueError("Packet status opened a source prematurely")

    root = packet_path.resolve().parents[1]
    for item in packet.get("basis", []):
        basis_path = _resolve_repo_path(root, str(item.get("path")))
        if not basis_path.is_file() or sha256_file(basis_path) != item.get("sha256"):
            raise ValueError(f"Missing or changed packet basis: {item.get('role')}")

    manifest = packet["submission_manifest"]
    if manifest["required_status"] != "PENDING_INDEPENDENT_INTAKE_QA":
        raise ValueError("Submission status no longer requires independent QA")
    for key in ("overwrite_existing_files_allowed",):
        if manifest[key] is not False:
            raise ValueError("No-overwrite contract was weakened")
    for key in ("original_bytes_must_be_preserved", "sha256_required", "one_manifest_item_per_file"):
        if manifest[key] is not True:
            raise ValueError("Immutable submission contract was weakened")

    schema_path = _resolve_repo_path(root, manifest["schema_path"])
    template_path = _resolve_repo_path(root, manifest["template_path"])
    schema = load_object(schema_path)
    template = load_object(template_path)
    if schema["properties"]["packet_id"].get("const") != EXPECTED_PACKET_ID:
        raise ValueError("Submission schema is not bound to the packet")
    if schema["properties"]["status"].get("const") != "PENDING_INDEPENDENT_INTAKE_QA":
        raise ValueError("Submission schema does not enforce pending QA")
    if template.get("packet_id") != EXPECTED_PACKET_ID or template.get("status") != "TEMPLATE_NOT_A_SUBMISSION":
        raise ValueError("Submission template can be confused with a real submission")

    sources = packet["source_instructions"]
    by_id = {item["source_id"]: item for item in sources}
    if set(by_id) != EXPECTED_SOURCES or len(by_id) != len(sources):
        raise ValueError("Manual-acquisition source set changed")
    for source_id, source in by_id.items():
        if source["maximum_items_per_submission"] > 20:
            raise ValueError(f"Unbounded manual submission: {source_id}")
        if source["automatic_ground_truth_allowed"] is not False:
            raise ValueError(f"Automatic ground truth opened: {source_id}")
        if source["candidate_enumeration_opened"] is not False:
            raise ValueError(f"Candidate enumeration opened: {source_id}")
        if not source["official_urls"] or not source["allowed_hosts"]:
            raise ValueError(f"Official URL/host allowlist missing: {source_id}")
        for url in source["official_urls"]:
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in source["allowed_hosts"]:
                raise ValueError(f"Non-official or non-HTTPS source URL: {source_id}")
        if source_id in BLOCKED_VIETNAMESE_SOURCES:
            if not source["activation_status"].startswith("BLOCKED_PENDING_"):
                raise ValueError(f"Vietnamese source opened prematurely: {source_id}")
            if "USER_SAVED_FIRST_PARTY_ARTIFACT" in source["permitted_acquisition_modes"]:
                raise ValueError(f"Vietnamese source permits unsupported manual capture: {source_id}")

    gate = packet["intake_acceptance_gate"]
    for key in (
        "qa_acceptance_creates_candidate",
        "qa_acceptance_creates_label",
        "qa_acceptance_opens_sampling_matrix_v2",
        "qa_acceptance_allows_model_input",
    ):
        if gate[key] is not False:
            raise ValueError(f"Intake acceptance gate opened: {key}")

    decision = packet["decision"]
    if decision["instructions_and_template_ready"] is not True:
        raise ValueError("Packet did not declare instructions ready")
    forbidden = (
        "dfpi_automated_collection_allowed",
        "vietnamese_reference_acquisition_allowed_now",
        "candidate_enumeration_allowed",
        "artifact_capture_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "training_allowed",
        "model_scoring_allowed",
    )
    if any(decision[key] is not False for key in forbidden):
        raise ValueError("Packet opened a collection, data, or model gate")

    return {
        "packet_id": packet["packet_id"],
        "source_count": len(sources),
        "dfpi_user_supplied_path_documented": True,
        "vietnamese_sources_blocked": sorted(BLOCKED_VIETNAMESE_SOURCES),
        "candidate_enumeration_allowed": decision["candidate_enumeration_allowed"],
        "training_allowed": decision["training_allowed"],
    }


def validate_submission(packet_path: Path, submission_path: Path, raw_root: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    verify(packet_path)
    submission = load_object(submission_path)
    if submission.get("packet_id") != EXPECTED_PACKET_ID:
        raise ValueError("Submission is not bound to the frozen packet")
    if submission.get("status") != "PENDING_INDEPENDENT_INTAKE_QA":
        raise ValueError("Submission must remain pending independent QA")
    items = submission.get("items")
    if not isinstance(items, list) or not items or len(items) > 20:
        raise ValueError("Submission must contain 1-20 items")

    by_id = {item["source_id"]: item for item in packet["source_instructions"]}
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    counts: dict[str, int] = {}
    for item in items:
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in seen_ids:
            raise ValueError("Item IDs must be non-empty and unique")
        seen_ids.add(item_id)
        source_id = item.get("source_id")
        if source_id not in by_id:
            raise ValueError(f"Unknown source ID: {source_id}")
        source = by_id[source_id]
        counts[source_id] = counts.get(source_id, 0) + 1
        if counts[source_id] > source["maximum_items_per_submission"]:
            raise ValueError(f"Source item limit exceeded: {source_id}")
        if source_id in BLOCKED_VIETNAMESE_SOURCES:
            raise ValueError(f"Vietnamese source remains blocked pending verified reuse basis: {source_id}")
        parsed = urlparse(str(item.get("official_source_url", "")))
        if parsed.scheme != "https" or parsed.hostname not in source["allowed_hosts"]:
            raise ValueError(f"Source URL is outside the official host allowlist: {item_id}")
        if item.get("acquisition_mode") not in source["permitted_acquisition_modes"]:
            raise ValueError(f"Acquisition mode is not permitted: {item_id}")
        rights = item.get("rights_basis")
        if not isinstance(rights, dict) or rights.get("basis_type") not in source["required_rights_basis_types"]:
            raise ValueError(f"Rights basis is not permitted: {item_id}")
        if item.get("redistribution_permitted") is not False:
            raise ValueError(f"Redistribution must remain disabled: {item_id}")
        if not isinstance(item.get("contains_personal_data"), bool):
            raise ValueError(f"Personal-data flag missing: {item_id}")
        relative = str(item.get("stored_relative_path", ""))
        posix = PurePosixPath(relative.replace("\\", "/"))
        if posix.is_absolute() or ".." in posix.parts or not posix.parts:
            raise ValueError(f"Unsafe stored path: {item_id}")
        if posix.parts[0] != source["destination_relative_directory"]:
            raise ValueError(f"Stored path is outside the exact source directory: {item_id}")
        normalized = posix.as_posix()
        if normalized in seen_paths:
            raise ValueError(f"Duplicate stored path: {normalized}")
        seen_paths.add(normalized)
        artifact_path = raw_root.joinpath(*posix.parts)
        if not artifact_path.is_file():
            raise ValueError(f"Submitted file is missing: {normalized}")
        if artifact_path.stat().st_size != item.get("byte_size"):
            raise ValueError(f"Submitted byte size mismatch: {normalized}")
        expected_hash = item.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or expected_hash.lower() != expected_hash:
            raise ValueError(f"Invalid lowercase SHA-256: {normalized}")
        if sha256_file(artifact_path) != expected_hash:
            raise ValueError(f"Submitted SHA-256 mismatch: {normalized}")

    return {
        "submission_id": submission.get("submission_id"),
        "status": submission["status"],
        "item_count": len(items),
        "source_counts": dict(sorted(counts.items())),
        "files_and_hashes_verified": True,
        "candidate_or_label_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--raw-root", type=Path)
    args = parser.parse_args()
    if bool(args.submission) != bool(args.raw_root):
        parser.error("--submission and --raw-root must be provided together")
    result = (
        validate_submission(args.packet, args.submission, args.raw_root)
        if args.submission
        else verify(args.packet)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
