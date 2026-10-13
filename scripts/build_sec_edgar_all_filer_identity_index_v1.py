"""Stream the verified SEC bulk ZIP into a compact all-filer identity index."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import (
    load_object,
    sha256_file,
)


PRIMARY_MEMBER = re.compile(r"^CIK([0-9]{10})\.json$")


def resolve_basis_path(config_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else config_path.resolve().parents[1] / path


def validate_protocol(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("amendment_id") != "ISI_SEC_EDGAR_SUBMISSIONS_BULK_V1_STORAGE_AMENDMENT_V1":
        raise ValueError("Unexpected SEC bulk storage amendment identity")
    if config.get("status") != "FROZEN_LOGICAL_JSON_EXTRACTION_APPROVED_LOOSE_FILE_EXPANSION_BLOCKED":
        raise PermissionError("SEC bulk logical extraction is not frozen as approved")
    for item in config.get("basis", []):
        path = resolve_basis_path(config_path, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"SEC bulk storage amendment basis mismatch: {item['role']}")
    decision = config.get("decision", {})
    if decision.get("logical_extraction_execution_allowed") is not True:
        raise PermissionError("SEC bulk logical extraction execution is closed")
    for gate in (
        "candidate_enumeration_allowed",
        "shortlist_materialization_allowed",
        "labeling_allowed",
        "validation_or_test_opening_allowed",
        "training_allowed",
    ):
        if decision.get(gate) is not False:
            raise PermissionError(f"SEC bulk storage amendment opened forbidden gate: {gate}")
    return config


def remove_failed_staging(staging: Path, output: Path) -> None:
    if not staging.exists():
        return
    if staging.resolve().parent != output.resolve().parent or staging.name != output.name + ".partial":
        raise RuntimeError("Refusing to remove an unexpected staging directory")
    shutil.rmtree(staging)


def build(config_path: Path) -> dict[str, Any]:
    config = validate_protocol(config_path)
    raw = Path(config["raw_input"]["path"])
    manifest = Path(config["raw_input"]["manifest_path"])
    if sha256_file(raw) != config["raw_input"]["sha256"]:
        raise ValueError("SEC bulk raw archive hash mismatch")
    if sha256_file(manifest) != config["raw_input"]["manifest_sha256"]:
        raise ValueError("SEC bulk manifest hash mismatch")

    logical = config["logical_extraction"]
    output = Path(logical["output_directory"])
    staging = output.with_name(output.name + ".partial")
    if output.exists() or staging.exists():
        raise FileExistsError("Refusing to overwrite SEC all-filer identity index output or staging")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    index_path = staging / logical["index_filename"]
    report_path = staging / logical["report_filename"]
    seen_ciks: set[str] = set()
    primary_members = 0
    selected = 0
    historical = 0
    non_json = 0
    empty_names = 0
    source_uncompressed_bytes = 0
    try:
        with zipfile.ZipFile(raw) as archive, index_path.open("x", encoding="utf-8", newline="\n") as out:
            infos = archive.infolist()
            if len(infos) != config["preflight"]["member_count"]:
                raise ValueError("SEC bulk member count differs from frozen preflight")
            for info in infos:
                match = PRIMARY_MEMBER.fullmatch(info.filename)
                if match:
                    primary_members += 1
                    cik_from_name = match.group(1)
                    with archive.open(info, "r") as member:
                        record = json.load(member)
                    cik_from_json = str(record.get("cik", "")).strip().zfill(10)
                    name = str(record.get("name", "")).strip()
                    if cik_from_json != cik_from_name:
                        raise ValueError("SEC primary submission filename/JSON CIK mismatch")
                    if cik_from_name in seen_ciks:
                        raise ValueError("SEC primary submission contains a duplicate CIK")
                    seen_ciks.add(cik_from_name)
                    if not name:
                        empty_names += 1
                        continue
                    out.write(
                        json.dumps(
                            {"cik": cik_from_name, "name": name},
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    selected += 1
                    source_uncompressed_bytes += info.file_size
                elif info.filename.casefold().endswith(".json"):
                    historical += 1
                elif not info.is_dir():
                    non_json += 1
            out.flush()
            os.fsync(out.fileno())

        expected = config["preflight"]
        if primary_members != expected["primary_submission_json_members"]:
            raise ValueError("SEC primary-member count differs from frozen preflight")
        if historical != expected["historical_submission_json_members"]:
            raise ValueError("SEC historical-member count differs from frozen preflight")
        if non_json != expected["non_json_members"]:
            raise ValueError("SEC non-JSON-member count differs from frozen preflight")
        if empty_names != expected["empty_name_primary_members"]:
            raise ValueError("SEC empty-name count differs from frozen schema audit")
        if selected != logical["expected_output_records"]:
            raise ValueError("SEC identity-index row count differs from frozen expectation")

        report = {
            "analysis_id": "ISI_SEC_EDGAR_ALL_FILER_IDENTITY_INDEX_V1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "FROZEN_LOGICAL_IDENTITY_INDEX_REFERENCE_ONLY",
            "input": {
                "raw_archive": str(raw),
                "raw_archive_sha256": config["raw_input"]["sha256"],
                "storage_amendment": str(config_path),
                "storage_amendment_sha256": sha256_file(config_path),
            },
            "output": {
                "identity_index": logical["index_filename"],
                "identity_index_sha256": sha256_file(index_path),
                "record_count": selected,
                "unique_cik_count": selected,
            },
            "scope": {
                "primary_submission_members_read": primary_members,
                "selected_primary_submission_members": selected,
                "excluded_historical_submission_members": historical,
                "excluded_non_json_members": non_json,
                "excluded_empty_name_primary_members": empty_names,
                "source_uncompressed_bytes_read": source_uncompressed_bytes,
                "fields_retained": ["cik", "name"],
                "candidate_urls_or_hosts_retained": 0,
            },
            "safety_contract": {
                "network_operations": 0,
                "candidate_records_enumerated": 0,
                "labels_created": 0,
                "model_operations": 0,
                "training_allowed": False,
            },
        }
        with report_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        staging.replace(output)
        report["output_directory"] = str(output)
        return report
    except Exception:
        remove_failed_staging(staging, output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
