"""Build one complete, quota-exact V1-Core channel contribution."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.verify_target_text_corpus_v1_sampling_matrix import verify as verify_matrix
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def _sha(value: Any, field: str, record_id: str) -> str:
    text = str(value)
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError(f"Invalid {field}: {record_id}")
    return text


def _time(value: Any, record_id: str) -> None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Invalid collected_at: {record_id}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"Timezone missing from collected_at: {record_id}")


def build(contract_path: Path, matrix_path: Path, candidate_manifest_path: Path, channel_id: str) -> dict[str, Any]:
    contract = load_object(contract_path)
    matrix = load_object(matrix_path)
    candidates = load_object(candidate_manifest_path)
    if contract.get("contract_id") != "ISI_TARGET_TEXT_CORPUS_V1_CORE_RELEASE_CONTRACT_V1":
        raise ValueError("Unexpected V1-Core contract")
    verify_matrix(matrix_path)
    if contract.get("sampling_matrix", {}).get("sha256") != sha256_file(matrix_path):
        raise ValueError("Contract/matrix binding mismatch")
    quota_by_id = {row["channel_id"]: row for row in matrix["channel_quotas"]}
    if channel_id not in quota_by_id:
        raise ValueError("Unknown channel ID")
    quota = quota_by_id[channel_id]
    if candidates.get("status") != "FROZEN_OWNER_ACCEPTED_CHANNEL_CANDIDATES" or candidates.get("channel_id") != channel_id:
        raise ValueError("Unexpected candidate manifest identity or status")
    if candidates.get("sampling_matrix_sha256") != sha256_file(matrix_path):
        raise ValueError("Candidate manifest/matrix binding mismatch")

    record_contract = contract["record_contract"]
    rows = list(candidates.get("records", []))
    ids = [str(row.get("record_id")) for row in rows]
    if len(ids) != len(set(ids)) or any(not value.strip() for value in ids):
        raise ValueError("Duplicate or empty record ID")
    counts = Counter(str(row.get("cohort")) for row in rows)
    expected = {"DEVELOPMENT": quota["development_accepted_group_quota"], "EXTERNAL_HOLDOUT": quota["external_holdout_accepted_group_quota"]}
    if counts != expected:
        raise ValueError(f"Channel quota mismatch: {dict(counts)} != {expected}")

    seen = {field: set() for field in record_contract["required_group_fields"]}
    text_hashes: set[str] = set()
    capture_hashes: set[str] = set()
    source_urls: set[str] = set()
    language_counts: Counter[str] = Counter()
    for row in rows:
        record_id = str(row["record_id"])
        if row.get("channel_id") != channel_id or row.get("target_status") != quota["target_status"]:
            raise ValueError(f"Channel/target mismatch: {record_id}")
        if row.get("evidence_confidence") != "HIGH" or row.get("review_status") != "RECONCILED_OWNER_ACCEPTED":
            raise ValueError(f"Review gate mismatch: {record_id}")
        expected_eligibility = "NO_PENDING_GROUP_SPLIT_RELEASE" if row.get("cohort") == "DEVELOPMENT" else "NO_EXTERNAL_HOLDOUT"
        expected_scoring = "NO" if row.get("cohort") == "DEVELOPMENT" else "NO_PENDING_FROZEN_EVALUATION_RELEASE"
        if row.get("release_eligibility") != expected_eligibility or row.get("model_scoring_eligibility") != expected_scoring:
            raise ValueError(f"Release or scoring eligibility mismatch: {record_id}")
        for field in record_contract["required_true_fields"]:
            if row.get(field) is not True:
                raise ValueError(f"Required gate {field} did not pass: {record_id}")
        for field in record_contract["required_sha256_fields"]:
            _sha(row.get(field), field, record_id)
        for field in record_contract["forbidden_fields"]:
            if field in row:
                raise ValueError(f"Forbidden model field {field}: {record_id}")
        text = row.get("observed_artifact_visible_text")
        if not isinstance(text, str) or len("".join(text.split())) < record_contract["minimum_non_whitespace_text_characters"]:
            raise ValueError(f"Observed text below minimum: {record_id}")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest != row["observed_artifact_text_sha256"] or digest in text_hashes:
            raise ValueError(f"Text hash mismatch or collision: {record_id}")
        text_hashes.add(digest)
        capture_hash = row["raw_capture_sha256"]
        if capture_hash in capture_hashes:
            raise ValueError(f"Raw capture collision: {record_id}")
        capture_hashes.add(capture_hash)
        source_url = str(row.get("source_url"))
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or parsed.hostname != "web.archive.org" or not re.match(r"^/web/\d{14}id_/https?://", parsed.path) or source_url in source_urls:
            raise ValueError(f"Invalid or duplicate raw archive URL: {record_id}")
        source_urls.add(source_url)
        _time(row.get("collected_at"), record_id)
        for field in record_contract["required_group_fields"]:
            value = str(row.get(field, "")).strip()
            if not value or value in seen[field]:
                raise ValueError(f"Missing or duplicate {field}: {record_id}")
            seen[field].add(value)
        language = str(row.get("language_code", "")).casefold()
        if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", language):
            raise ValueError(f"Missing reviewed language: {record_id}")
        primary = language.split("-", 1)[0]
        language_counts[f"{row['cohort']}:NON_ENGLISH"] += primary not in contract["language_contract"]["english_codes"]
        language_counts[f"{row['cohort']}:VIETNAMESE"] += primary in contract["language_contract"]["vietnamese_codes"]

    prefix = {"DEVELOPMENT": "development", "EXTERNAL_HOLDOUT": "external_holdout"}
    for cohort in expected:
        for kind, suffix in (("NON_ENGLISH", "minimum_non_english_groups_per_label"), ("VIETNAMESE", "minimum_vietnamese_groups_per_label")):
            minimum = contract["language_contract"][f"{prefix[cohort]}_{suffix}"]
            if language_counts[f"{cohort}:{kind}"] < minimum:
                raise ValueError(f"Language quota not met: {cohort}/{kind}")

    return {
        "contribution_id": f"ISI_TARGET_TEXT_CORPUS_V1_{channel_id}_CONTRIBUTION_V1",
        "status": "PASS_CHANNEL_CONTRIBUTION_READY",
        "channel_id": channel_id,
        "target_status": quota["target_status"],
        "inputs": {"contract_sha256": sha256_file(contract_path), "sampling_matrix_sha256": sha256_file(matrix_path), "candidate_manifest_sha256": sha256_file(candidate_manifest_path)},
        "record_ids": ids,
        "counts": {"DEVELOPMENT": counts["DEVELOPMENT"], "EXTERNAL_HOLDOUT": counts["EXTERNAL_HOLDOUT"], "total": len(rows)},
        "language_counts": dict(sorted(language_counts.items())),
        "decision": {"dataset_release_contribution_allowed": True, "partial_contribution_allowed": False, "training_allowed": False, "model_scoring_allowed": False},
        "safety_contract": {"network_operations": 0, "model_operations": 0, "training_operations": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite channel contribution")
    result = build(args.contract, args.matrix, args.candidate_manifest, args.channel_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({"contribution_id": result["contribution_id"], "channel_id": result["channel_id"], "counts": result["counts"], "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
