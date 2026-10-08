"""Extract exact visible text from audited Target Text Corpus V1 captures offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_text import extract_visible_text
from src.isi.normalization.wayback_external_text import decode_archived_payload


CANDIDATE_ID = re.compile(r"^TTCV1_CAND_[A-Z0-9_]+$")
EXPECTED_CAPTURE_REPORT_ID = "ISI_TARGET_TEXT_CORPUS_V1_WAYBACK_CAPTURE_REPORT_V2"
EXPECTED_CAPTURE_QA_STATUS = "PASS_23_RAW_CAPTURES_6_SMALL_RESPONSES_PRESERVED"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}")
            rows.append(value)
    return rows


def resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def validate_input_hash(root: Path, item: dict[str, Any], role: str) -> Path:
    path = resolve(root, item.get("path", ""))
    if not path.is_file():
        raise FileNotFoundError(f"Missing {role}: {path}")
    actual = sha256_file(path)
    if actual != item.get("sha256"):
        raise ValueError(f"{role} SHA-256 mismatch: {actual}")
    return path


def prepare_extraction(config_path: Path) -> tuple[dict[str, Any], list[tuple[dict[str, Any], bytes]], dict[str, Path]]:
    """Validate every input and compute every output byte before writing anything."""

    config = load_json(config_path)
    if config.get("extraction_id") != "ISI_TARGET_TEXT_CORPUS_V1_EXACT_TEXT_EXTRACTION_V1":
        raise ValueError("Unexpected extraction ID")
    root = config_path.resolve().parents[1]
    inputs = config.get("inputs", {})
    paths = {
        role: validate_input_hash(root, inputs.get(role, {}), role)
        for role in (
            "protocol", "capture_result_registry", "candidate_queue",
            "capture_report", "capture_independent_qa",
        )
    }
    safety = config.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("live_domain_access_allowed") is not False:
        raise ValueError("Extraction configuration must be offline")
    if any(safety.get(key) != 0 for key in (
        "labels_created", "labels_changed", "model_fit_operations",
        "model_scoring_operations", "validation_or_test_openings",
    )):
        raise ValueError("Extraction configuration violates the no-label/no-model gate")

    capture_report = load_json(paths["capture_report"])
    capture_qa = load_json(paths["capture_independent_qa"])
    registry = load_json(paths["capture_result_registry"])
    if capture_report.get("report_id") != EXPECTED_CAPTURE_REPORT_ID:
        raise ValueError("Unexpected capture report ID")
    if capture_qa.get("status") != EXPECTED_CAPTURE_QA_STATUS:
        raise ValueError("Independent raw-capture QA has not passed")
    if registry.get("decision", {}).get("exact_text_extraction_allowed_for_captured_rows") is not True:
        raise ValueError("Capture-result registry has not released exact-text extraction")
    if registry.get("decision", {}).get("binary_labeling_allowed") is not False:
        raise ValueError("Binary-labeling gate unexpectedly open")

    candidates = load_jsonl(paths["candidate_queue"])
    by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id", ""))
        if not CANDIDATE_ID.fullmatch(candidate_id) or candidate_id in by_id:
            raise ValueError(f"Invalid or duplicate candidate ID: {candidate_id}")
        by_id[candidate_id] = candidate

    captured = [row for row in capture_report.get("results", []) if row.get("outcome") == "CAPTURED"]
    failed = [row for row in capture_report.get("results", []) if row.get("outcome") == "FAILED"]
    expected = config.get("expected_input", {})
    if len(captured) != expected.get("captured_count") or len(failed) != expected.get("failed_count_preserved"):
        raise ValueError("Captured/failed population changed")
    distribution = Counter(str(row.get("channel_id")) for row in captured)
    if dict(distribution) != expected.get("captured_by_channel"):
        raise ValueError(f"Captured channel distribution changed: {dict(distribution)}")
    if len({str(row.get("candidate_id")) for row in captured}) != len(captured):
        raise ValueError("Duplicate captured candidate ID")

    minimum = int(config.get("method", {}).get("minimum_non_whitespace_text_characters", -1))
    if minimum != 20:
        raise ValueError("Frozen minimum non-whitespace threshold must equal 20")
    prepared: list[tuple[dict[str, Any], bytes]] = []
    for capture in sorted(captured, key=lambda row: str(row["candidate_id"])):
        candidate_id = str(capture["candidate_id"])
        candidate = by_id.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Captured row absent from candidate queue: {candidate_id}")
        if capture.get("channel_id") != candidate.get("channel_id"):
            raise ValueError(f"Channel mismatch: {candidate_id}")
        if capture.get("channel_target_stratum") != candidate.get("channel_target_stratum"):
            raise ValueError(f"Target-stratum mismatch: {candidate_id}")
        raw_path = Path(str(capture.get("capture_path", "")))
        if not raw_path.is_file():
            raise FileNotFoundError(f"Raw capture missing: {candidate_id}")
        raw = raw_path.read_bytes()
        if len(raw) != capture.get("bytes") or sha256_bytes(raw) != capture.get("sha256"):
            raise ValueError(f"Raw capture byte/hash mismatch: {candidate_id}")
        decoded, transport = decode_archived_payload(raw)
        text, canonical_urls = extract_visible_text(decoded)
        text_bytes = text.encode("utf-8")
        non_whitespace = len(re.sub(r"\s+", "", text))
        text_path = Path(str(config["outputs"]["text_root"])) / f"{candidate_id}.txt"
        manifest = {
            "schema_version": "target_text_exact_extraction_v1",
            "candidate_id": candidate_id,
            "channel_id": capture["channel_id"],
            "channel_target_stratum": capture["channel_target_stratum"],
            "candidate_host": capture["candidate_host"],
            "source_id": candidate["reference"]["source_id"],
            "source_record_id": candidate["reference"]["source_record_id"],
            "source_url": candidate["reference"]["source_url"],
            "snapshot_timestamp": capture["snapshot_timestamp"],
            "archive_url": capture.get("final_archive_url") or capture["requested_archive_url"],
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

    outputs = {
        "text_root": Path(str(config["outputs"]["text_root"])),
        "manifest": Path(str(config["outputs"]["manifest"])),
        "report": Path(str(config["outputs"]["report"])),
    }
    return config, prepared, outputs


def execute(config_path: Path) -> dict[str, Any]:
    config, prepared, outputs = prepare_extraction(config_path)
    if outputs["text_root"].exists():
        raise FileExistsError(f"Refusing to overwrite frozen output directory: {outputs['text_root']}")
    for role in ("manifest", "report"):
        if outputs[role].exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {outputs[role]}")

    outputs["text_root"].mkdir(parents=True, exist_ok=False)
    for row, text_bytes in prepared:
        text_path = Path(str(row["text_path"]))
        if text_path.parent.resolve() != outputs["text_root"].resolve():
            raise ValueError(f"Text output escaped frozen directory: {text_path}")
        with text_path.open("xb") as handle:
            handle.write(text_bytes)
    outputs["manifest"].parent.mkdir(parents=True, exist_ok=True)
    with outputs["manifest"].open("x", encoding="utf-8", newline="\n") as handle:
        for row, _ in prepared:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    channel_gate = Counter(
        (str(row["channel_id"]), str(row["content_gate_state"])) for row, _ in prepared
    )
    transport_counts = Counter(str(row["transport_decoding"]) for row, _ in prepared)
    passed = sum(bool(row["minimum_content_passed"]) for row, _ in prepared)
    report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_EXACT_TEXT_EXTRACTION_REPORT_V1",
        "created_at": "2026-10-08",
        "status": "OFFLINE_EXTRACTION_COMPLETE_INDEPENDENT_QA_REQUIRED",
        "config": {"path": str(config_path), "sha256": sha256_file(config_path)},
        "counts": {
            "extracted_count": len(prepared),
            "minimum_content_passed_count": passed,
            "below_minimum_preserved_count": len(prepared) - passed,
            "transport_decoding": dict(sorted(transport_counts.items())),
            "content_gate_by_channel": [
                {"channel_id": channel, "content_gate_state": state, "count": count}
                for (channel, state), count in sorted(channel_gate.items())
            ],
            "labels_created": 0,
        },
        "outputs": {
            "text_root": str(outputs["text_root"]),
            "text_file_count": len(prepared),
            "manifest": {"path": str(outputs["manifest"]), "sha256": sha256_file(outputs["manifest"])},
        },
        "gates": {
            "independent_byte_for_byte_qa_required": True,
            "post_capture_exclusion_and_grouping_required": True,
            "human_label_review_allowed": False,
            "model_scoring_allowed": False,
            "training_allowed": False,
        },
        "safety_contract": config["safety_contract"],
    }
    with outputs["report"].open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    report = execute(args.config)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
