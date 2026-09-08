"""Read-only ingestion support for Mendeley Investment-Related Deceptive Content V2."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SOURCE_ID = "mendeley_investment_deceptive_2026"
SOURCE_URL = "https://data.mendeley.com/datasets/6wnd7jrt6z/2"
SOURCE_VERSION = "2"
LICENSE = "CC BY 4.0"
RAW_LABEL_SEMANTICS = (
    "Harmonized investment-related deceptive or suspicious content labels; "
    "not verified investment-scam ground truth for every record."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profile_csv(path: Path) -> dict[str, object]:
    """Return a compact, non-content profile without retaining raw records."""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("CSV does not contain a header row")
        columns = reader.fieldnames
        missing = Counter({column: 0 for column in columns})
        rows = 0
        for row in reader:
            rows += 1
            for column in columns:
                if not (row.get(column) or "").strip():
                    missing[column] += 1
    return {
        "row_count": rows,
        "column_count": len(columns),
        "columns": columns,
        "missing_value_count_by_column": dict(missing),
    }


def ingest_csv(
    input_path: Path,
    raw_root: Path,
    manifest_root: Path,
    report_root: Path,
    collected_at: datetime | None = None,
) -> tuple[Path, Path, Path]:
    """Copy one local Mendeley CSV immutably, then create manifest and profile."""
    if input_path.suffix.lower() != ".csv":
        raise ValueError("Mendeley adapter currently accepts a CSV file")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    collected_at = collected_at or datetime.now(timezone.utc)
    date_label = collected_at.date().isoformat()
    destination_dir = raw_root / SOURCE_ID / f"v{SOURCE_VERSION}"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / input_path.name
    if destination.exists() and sha256_file(destination) != sha256_file(input_path):
        raise FileExistsError(f"Refusing to overwrite immutable raw file: {destination}")
    if not destination.exists():
        shutil.copy2(input_path, destination)

    profile = profile_csv(destination)
    checksum = sha256_file(destination)
    relative_storage = destination.as_posix()
    manifest = {
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "downloaded_at": collected_at.isoformat(),
        "source_version": SOURCE_VERSION,
        "license_or_terms": LICENSE,
        "raw_label_semantics": RAW_LABEL_SEMANTICS,
        "raw_file_sha256": checksum,
        "storage_path": relative_storage,
    }
    manifest_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_root / f"{SOURCE_ID}__v{SOURCE_VERSION}__{date_label}.json"
    report_path = report_root / f"{SOURCE_ID}__v{SOURCE_VERSION}__{date_label}__profile.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination, manifest_path, report_path
