"""Audit whether the local Mendeley V2 deposit contains usable image assets.

The audit is deliberately read-only for source files and never emits raw text.
It distinguishes image-related metadata flags from actual image bytes or paths.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


SOURCE_ID = "mendeley_investment_deceptive_2026"
SOURCE_VERSION = "2"
EXPECTED_COLUMNS = 32
EXPECTED_RECORDS = 16_202
IMAGE_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
IMAGE_REFERENCE = re.compile(
    r"(?i)(?:^data:image/|^https?://|^file:|[\\/]|\.(?:jpe?g|png|gif|webp|bmp|tiff?)(?:\b|[?#]))"
)
TEXT_IMAGE_EXTENSION = re.compile(r"(?i)\.(?:jpe?g|png|gif|webp|bmp|tiff?)(?:\b|[?#])")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_image_related_column(column: str) -> bool:
    lowered = column.lower()
    return any(token in lowered for token in ("image", "photo", "picture", "media", "video"))


def audit_csv(path: Path) -> dict[str, object]:
    modality_counts: Counter[str] = Counter()
    metadata_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    modality_by_label: dict[str, Counter[str]] = defaultdict(Counter)
    candidate_column_counts: dict[str, Counter[str]] = {}
    candidate_reference_counts: Counter[str] = Counter()
    record_count = 0
    text_image_extension_mentions = 0
    text_http_mentions = 0

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("CSV does not contain a header row")
        columns = list(reader.fieldnames)
        candidate_columns = [column for column in columns if is_image_related_column(column)]
        candidate_column_counts = {column: Counter() for column in candidate_columns}

        for row in reader:
            record_count += 1
            modality = (row.get("source_modality") or "<MISSING>").strip()
            has_metadata = (row.get("has_metadata") or "<MISSING>").strip()
            label = (row.get("label") or "<MISSING>").strip()
            modality_counts[modality] += 1
            metadata_counts[has_metadata] += 1
            label_counts[label] += 1
            modality_by_label[modality][label] += 1

            for column in candidate_columns:
                value = (row.get(column) or "").strip()
                candidate_column_counts[column][value or "<MISSING>"] += 1
                if value and IMAGE_REFERENCE.search(value):
                    candidate_reference_counts[column] += 1

            text = row.get("text_content") or ""
            if TEXT_IMAGE_EXTENSION.search(text):
                text_image_extension_mentions += 1
            if re.search(r"(?i)https?://", text):
                text_http_mentions += 1

    return {
        "record_count": record_count,
        "column_count": len(columns),
        "columns": columns,
        "source_modality_counts": dict(modality_counts),
        "has_metadata_counts": dict(metadata_counts),
        "label_counts": dict(label_counts),
        "source_modality_by_label": {
            modality: dict(counts) for modality, counts in modality_by_label.items()
        },
        "image_related_columns": candidate_columns,
        "image_related_column_value_counts": {
            column: dict(counts) for column, counts in candidate_column_counts.items()
        },
        "actual_image_reference_count_by_column": dict(candidate_reference_counts),
        "text_records_mentioning_image_extension": text_image_extension_mentions,
        "text_records_containing_http_url": text_http_mentions,
    }


def inspect_xlsx(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"present": False}
    if not path.is_file():
        return {"present": False, "path": str(path)}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    media_entries = sorted(name for name in names if name.startswith("xl/media/"))
    external_links = sorted(name for name in names if name.startswith("xl/externalLinks/"))
    drawing_entries = sorted(name for name in names if name.startswith("xl/drawings/"))
    return {
        "present": True,
        "path": str(path),
        "sha256": sha256_file(path),
        "embedded_media_entry_count": len(media_entries),
        "embedded_media_entries": media_entries,
        "external_link_entry_count": len(external_links),
        "drawing_entry_count": len(drawing_entries),
    }


def find_local_image_files(folder: Path) -> list[str]:
    return sorted(
        str(path)
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def run_audit(csv_path: Path, xlsx_path: Path | None) -> dict[str, object]:
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    csv_profile = audit_csv(csv_path)
    xlsx_profile = inspect_xlsx(xlsx_path)
    local_images = find_local_image_files(csv_path.parent)
    actual_reference_total = sum(csv_profile["actual_image_reference_count_by_column"].values())
    embedded_media_count = int(xlsx_profile.get("embedded_media_entry_count", 0))

    checks = {
        "expected_record_count": csv_profile["record_count"] == EXPECTED_RECORDS,
        "expected_column_count": csv_profile["column_count"] == EXPECTED_COLUMNS,
        "csv_has_image_path_or_bytes": actual_reference_total > 0,
        "raw_folder_has_image_files": bool(local_images),
        "xlsx_has_embedded_media": embedded_media_count > 0,
    }
    has_usable_image_assets = any(
        (
            checks["csv_has_image_path_or_bytes"],
            checks["raw_folder_has_image_files"],
            checks["xlsx_has_embedded_media"],
        )
    )
    return {
        "audit_id": "MENDELEY_IMAGE_READINESS_V1",
        "created_at": date.today().isoformat(),
        "source_id": SOURCE_ID,
        "source_version": SOURCE_VERSION,
        "input": {
            "csv_path": str(csv_path),
            "csv_sha256": sha256_file(csv_path),
            "xlsx_companion_path": str(xlsx_path) if xlsx_path else None,
        },
        "csv_profile": csv_profile,
        "xlsx_profile": xlsx_profile,
        "raw_folder_image_file_count": len(local_images),
        "raw_folder_image_files": local_images,
        "checks": checks,
        "decision": {
            "status": "READY" if has_usable_image_assets else "BLOCKED_NO_IMAGE_ASSETS",
            "has_usable_image_assets": has_usable_image_assets,
            "image_model_training_allowed": has_usable_image_assets,
            "meaning": (
                "Current local deposit contains usable image assets."
                if has_usable_image_assets
                else "Current local deposit supports text plus behavioral metadata, not image-model training."
            ),
            "default_profile_image_flag_meaning": (
                "Behavioral metadata indicating whether an account uses a default profile image; "
                "it is not an image file, image path, or pixel representation."
            ),
        },
        "safety_contract": {
            "network_operations": 0,
            "labels_created": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
            "raw_files_modified": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_audit(args.csv, args.xlsx)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["decision"]["status"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
