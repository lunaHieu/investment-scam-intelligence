"""Verify a proposed balanced Dataset V1-Core release without opening model data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.verify_target_text_corpus_v1_sampling_matrix import verify as verify_sampling_matrix


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


def resolve(root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def require_sha256(value: Any, field: str, record_id: str) -> str:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"Invalid {field}: {record_id}")
    return text


def parse_timestamp(value: Any, field: str, record_id: str) -> None:
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Invalid {field}: {record_id}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"Timezone missing from {field}: {record_id}")


def verify(contract_path: Path, manifest_path: Path) -> dict[str, Any]:
    contract = load_object(contract_path)
    manifest = load_object(manifest_path)
    root = contract_path.resolve().parents[1]
    if contract.get("contract_id") != "ISI_TARGET_TEXT_CORPUS_V1_CORE_RELEASE_CONTRACT_V1":
        raise ValueError("Unexpected core-release contract")
    if any(contract.get("release_decision", {}).values()):
        raise ValueError("Predeclared contract prematurely opens a release or model gate")

    matrix_ref = contract["sampling_matrix"]
    matrix_path = resolve(root, matrix_ref["path"])
    if not matrix_path.is_file() or sha256_file(matrix_path) != matrix_ref["sha256"]:
        raise ValueError("Sampling matrix path or hash mismatch")
    verify_sampling_matrix(matrix_path)
    matrix = load_object(matrix_path)

    expected = contract["expected_manifest"]
    if manifest.get("release_id") != expected["release_id"] or manifest.get("status") != expected["status"]:
        raise ValueError("Unexpected proposed release identity or status")
    if manifest.get("sampling_matrix_sha256") != sha256_file(matrix_path):
        raise ValueError("Proposed release is not bound to the frozen sampling matrix")
    decision = manifest.get("decision", {})
    if decision.get("independent_qa_passed") is not False or decision.get("development_group_split_plan_allowed") is not False:
        raise ValueError("Proposed release claims an independent QA or downstream split decision prematurely")
    if decision.get("training_allowed") is not False or decision.get("validation_or_test_opening_allowed") is not False or decision.get("external_holdout_model_scoring_allowed") is not False:
        raise ValueError("Proposed release prematurely opens a model gate")

    quotas = {row["channel_id"]: row for row in matrix["channel_quotas"]}
    contributions = list(manifest.get("channel_contributions", []))
    contribution_ids = [str(item.get("channel_id")) for item in contributions]
    if len(contribution_ids) != len(set(contribution_ids)) or set(contribution_ids) != set(quotas):
        raise ValueError("Channel-contribution population differs from the sampling matrix")
    contribution_by_channel: dict[str, dict[str, Any]] = {}
    release_root = manifest_path.resolve().parent
    for descriptor in contributions:
        channel_id = str(descriptor["channel_id"])
        contribution_path = resolve(release_root, descriptor.get("path")).resolve()
        if contribution_path.parent != release_root and release_root not in contribution_path.parents:
            raise ValueError(f"Channel contribution escaped the release directory: {channel_id}")
        if not contribution_path.is_file() or sha256_file(contribution_path) != descriptor.get("sha256"):
            raise ValueError(f"Channel contribution path or hash mismatch: {channel_id}")
        contribution = load_object(contribution_path)
        if contribution.get("status") != expected["channel_contribution_status"] or contribution.get("channel_id") != channel_id:
            raise ValueError(f"Channel contribution identity or status mismatch: {channel_id}")
        if contribution.get("decision", {}).get("dataset_release_contribution_allowed") is not True or contribution.get("decision", {}).get("training_allowed") is not False:
            raise ValueError(f"Channel contribution decision mismatch: {channel_id}")
        contribution_by_channel[channel_id] = {
            "sha256": descriptor["sha256"],
            "record_ids": [str(value) for value in contribution.get("record_ids", [])],
        }

    records = list(manifest.get("records", []))
    record_ids = [str(row.get("record_id")) for row in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Duplicate release record ID")
    if len(records) != matrix["cohorts"]["development"]["target_groups"]["total"] + matrix["cohorts"]["untouched_external_holdout"]["target_groups"]["total"]:
        raise ValueError("Release record count does not match frozen matrix")

    record_contract = contract["record_contract"]
    archive_contract = contract["archive_contract"]
    counts: Counter[tuple[str, str, str]] = Counter()
    label_counts: Counter[tuple[str, str]] = Counter()
    language_counts: Counter[tuple[str, str, str]] = Counter()
    channel_record_ids: dict[str, list[str]] = defaultdict(list)
    seen_groups: dict[str, set[str]] = {field: set() for field in record_contract["required_group_fields"]}
    seen_text_hashes: set[str] = set()
    seen_capture_hashes: set[str] = set()
    seen_urls: set[str] = set()

    for row in records:
        raw_record_id = row.get("record_id")
        if not isinstance(raw_record_id, str) or not raw_record_id.strip():
            raise ValueError("Release record ID is missing or invalid")
        record_id = raw_record_id
        target_status = str(row.get("target_status"))
        channel_id = str(row.get("channel_id"))
        cohort = str(row.get("cohort"))
        if target_status not in record_contract["allowed_target_statuses"] or cohort not in record_contract["allowed_cohorts"]:
            raise ValueError(f"Invalid target status or cohort: {record_id}")
        if channel_id not in quotas or quotas[channel_id]["target_status"] != target_status:
            raise ValueError(f"Channel/target mismatch: {record_id}")
        for field in record_contract["forbidden_fields"]:
            if field in row:
                raise ValueError(f"Forbidden pre-release field {field}: {record_id}")
        for field in record_contract["required_true_fields"]:
            if row.get(field) is not True:
                raise ValueError(f"Required gate {field} did not pass: {record_id}")
        if row.get("evidence_confidence") != record_contract["required_evidence_confidence"] or row.get("review_status") != record_contract["required_review_status"]:
            raise ValueError(f"Review confidence or status mismatch: {record_id}")
        for field in record_contract["required_sha256_fields"]:
            require_sha256(row.get(field), field, record_id)

        text = row.get("observed_artifact_visible_text")
        if not isinstance(text, str) or len("".join(text.split())) < record_contract["minimum_non_whitespace_text_characters"]:
            raise ValueError(f"Observed artifact text is below minimum: {record_id}")
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if text_hash != row["observed_artifact_text_sha256"]:
            raise ValueError(f"Observed artifact text hash mismatch: {record_id}")
        if text_hash in seen_text_hashes:
            raise ValueError(f"Exact text collision across release records: {record_id}")
        seen_text_hashes.add(text_hash)
        capture_hash = row["raw_capture_sha256"]
        if capture_hash in seen_capture_hashes:
            raise ValueError(f"Raw capture collision across release records: {record_id}")
        seen_capture_hashes.add(capture_hash)

        source_url = str(row.get("source_url"))
        parsed_url = urlparse(source_url)
        if parsed_url.scheme != archive_contract["scheme"] or parsed_url.hostname not in archive_contract["allowed_hosts"]:
            raise ValueError(f"Source URL is outside the archive-only contract: {record_id}")
        if archive_contract.get("raw_replay_modifier_required") is not True or not re.match(r"^/web/\d{14}id_/https?://", parsed_url.path):
            raise ValueError(f"Source URL is not a raw Wayback replay: {record_id}")
        if source_url in seen_urls:
            raise ValueError(f"Duplicate source URL: {record_id}")
        seen_urls.add(source_url)
        parse_timestamp(row.get("collected_at"), "collected_at", record_id)

        for field in record_contract["required_group_fields"]:
            value = str(row.get(field, "")).strip()
            if not value or value in seen_groups[field]:
                raise ValueError(f"Missing or overlapping {field}: {record_id}")
            seen_groups[field].add(value)

        language = str(row.get("language_code", "")).strip().lower()
        if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", language):
            raise ValueError(f"Missing reviewed language code: {record_id}")
        primary_language = language.split("-", 1)[0]
        language_class = "ENGLISH" if primary_language in contract["language_contract"]["english_codes"] else "NON_ENGLISH"
        language_counts[(cohort, target_status, language_class)] += 1
        if primary_language in contract["language_contract"]["vietnamese_codes"]:
            language_counts[(cohort, target_status, "VIETNAMESE")] += 1

        expected_eligibility = expected["development_release_eligibility"] if cohort == "DEVELOPMENT" else expected["external_holdout_release_eligibility"]
        if row.get("release_eligibility") != expected_eligibility:
            raise ValueError(f"Release eligibility mismatch: {record_id}")
        expected_scoring = "NO" if cohort == "DEVELOPMENT" else expected["external_holdout_model_scoring_eligibility"]
        if row.get("model_scoring_eligibility") != expected_scoring:
            raise ValueError(f"Model-scoring eligibility mismatch: {record_id}")
        if row["channel_contribution_qa_sha256"] != contribution_by_channel[channel_id]["sha256"]:
            raise ValueError(f"Channel-contribution binding mismatch: {record_id}")

        counts[(cohort, target_status, channel_id)] += 1
        label_counts[(cohort, target_status)] += 1
        channel_record_ids[channel_id].append(record_id)

    for channel_id, quota in quotas.items():
        target_status = quota["target_status"]
        if counts[("DEVELOPMENT", target_status, channel_id)] != quota["development_accepted_group_quota"]:
            raise ValueError(f"Development channel quota mismatch: {channel_id}")
        if counts[("EXTERNAL_HOLDOUT", target_status, channel_id)] != quota["external_holdout_accepted_group_quota"]:
            raise ValueError(f"External-holdout channel quota mismatch: {channel_id}")
        expected_ids = sorted(contribution_by_channel[channel_id]["record_ids"])
        if len(expected_ids) != len(set(expected_ids)) or expected_ids != sorted(channel_record_ids[channel_id]):
            raise ValueError(f"Channel contribution record population mismatch: {channel_id}")

    for cohort, matrix_key in (("DEVELOPMENT", "development"), ("EXTERNAL_HOLDOUT", "untouched_external_holdout")):
        for target_status in record_contract["allowed_target_statuses"]:
            if label_counts[(cohort, target_status)] != matrix["cohorts"][matrix_key]["target_groups"][target_status]:
                raise ValueError(f"Class quota mismatch: {cohort}/{target_status}")
            prefix = "development" if cohort == "DEVELOPMENT" else "external_holdout"
            language_contract = contract["language_contract"]
            if language_counts[(cohort, target_status, "NON_ENGLISH")] < language_contract[f"{prefix}_minimum_non_english_groups_per_label"]:
                raise ValueError(f"Non-English quota not met: {cohort}/{target_status}")
            if language_counts[(cohort, target_status, "VIETNAMESE")] < language_contract[f"{prefix}_minimum_vietnamese_groups_per_label"]:
                raise ValueError(f"Vietnamese quota not met: {cohort}/{target_status}")

    return {
        "verification_id": "ISI_TARGET_TEXT_CORPUS_V1_CORE_RELEASE_INDEPENDENT_QA_V1",
        "status": "PASS_BALANCED_GROUPED_RELEASE_PARTITION_PLAN_REQUIRED",
        "inputs": {
            "contract_sha256": sha256_file(contract_path),
            "manifest_sha256": sha256_file(manifest_path),
            "sampling_matrix_sha256": sha256_file(matrix_path),
        },
        "checks": {
            "record_count": len(records),
            "development_groups": sum(value for (cohort, _), value in label_counts.items() if cohort == "DEVELOPMENT"),
            "external_holdout_groups": sum(value for (cohort, _), value in label_counts.items() if cohort == "EXTERNAL_HOLDOUT"),
            "channel_count": len(quotas),
            "unique_text_hashes": len(seen_text_hashes),
            "unique_capture_hashes": len(seen_capture_hashes),
            "group_overlap_count": 0,
        },
        "decision": {
            "balanced_release_qa_passed": True,
            "development_group_split_plan_may_be_prepared": True,
            "training_allowed_now": False,
            "validation_or_test_opening_allowed": False,
            "external_holdout_model_scoring_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "model_operations": 0,
            "training_operations": 0,
            "validation_or_test_openings": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.contract, args.manifest)
    if args.output:
        if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
            raise FileExistsError("Refusing to overwrite core-release QA")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".partial")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
