"""Read-only ingestion support for the pinned Crimson website dataset."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SOURCE_ID = "crimson_www_2025"
SOURCE_URL = "https://github.com/pragseclab/Crimson"
LICENSE = "GPL-3.0"
RAW_LABEL_SEMANTICS = (
    "Research-detected cryptocurrency investment-scam websites; "
    "not a legal finding and not eligible for real-world Gold evaluation."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profile_json(path: Path) -> dict[str, object]:
    """Profile JSON structure without following or requesting any listed URL."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Crimson data.json must contain a top-level JSON list")
    if not all(isinstance(record, dict) for record in data):
        raise ValueError("Crimson data.json records must be JSON objects")
    key_counts: Counter[str] = Counter()
    for record in data:
        key_counts.update(record.keys())
    return {
        "top_level_type": "list",
        "row_count": len(data),
        "field_presence_count": dict(sorted(key_counts.items())),
        "sample_keys": sorted(key_counts)[:30],
        "profile_policy": "No listed domain or URL was requested during profiling.",
    }


def ingest_json(
    input_path: Path,
    raw_root: Path,
    manifest_root: Path,
    report_root: Path,
    commit_sha: str,
    collected_at: datetime | None = None,
) -> tuple[Path, Path, Path]:
    """Copy pinned JSON immutably, then create a manifest and structural profile."""
    if len(commit_sha) != 40 or any(char not in "0123456789abcdef" for char in commit_sha.lower()):
        raise ValueError("Crimson commit_sha must be a 40-character hexadecimal SHA")
    if input_path.suffix.lower() != ".json":
        raise ValueError("Crimson adapter currently accepts the repository data.json file")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    collected_at = collected_at or datetime.now(timezone.utc)
    date_label = collected_at.date().isoformat()
    destination_dir = raw_root / SOURCE_ID / commit_sha
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / input_path.name
    if destination.exists() and sha256_file(destination) != sha256_file(input_path):
        raise FileExistsError(f"Refusing to overwrite immutable raw file: {destination}")
    if not destination.exists():
        shutil.copy2(input_path, destination)

    profile = profile_json(destination)
    manifest = {
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "downloaded_at": collected_at.isoformat(),
        "source_version": commit_sha,
        "license_or_terms": LICENSE,
        "raw_label_semantics": RAW_LABEL_SEMANTICS,
        "raw_file_sha256": sha256_file(destination),
        "storage_path": destination.as_posix(),
    }
    manifest_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_root / f"{SOURCE_ID}__{commit_sha[:12]}__{date_label}.json"
    report_path = report_root / f"{SOURCE_ID}__{commit_sha[:12]}__{date_label}__profile.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination, manifest_path, report_path
