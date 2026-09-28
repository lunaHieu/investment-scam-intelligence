"""Independently verify ISI raw files against their checked-in manifests.

This script reads files only. It never downloads, changes, or requests listed URLs.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = ROOT / "registry" / "manifests"
SUPPORTED_SOURCE_IDS = {
    "mendeley_investment_deceptive_2026",
    "crimson_www_2025",
    "iosco_i_scan",
    "sec_iapd",
    "sec_iapd_homepage_capture_2026_09_24",
    "wayback_confirmed_capture_2026_09_24",
    "official_warning_capture_2026_09_24",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_profile(source_id: str, path: Path) -> dict[str, object]:
    if source_id in {"mendeley_investment_deceptive_2026", "iosco_i_scan"}:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file)
            header = next(reader)
            rows = sum(1 for _ in reader)
        return {"format": "CSV", "row_count": rows, "column_count": len(header), "columns": header}
    if source_id == "crimson_www_2025":
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise ValueError("Crimson raw file does not have the expected list-of-objects structure")
        fields = sorted({field for item in records for field in item})
        return {"format": "JSON", "row_count": len(records), "fields": fields}
    if source_id == "sec_iapd":
        root_element = None
        firm_count = 0
        with gzip.open(path, "rb") as file:
            for event, element in ET.iterparse(file, events=("start", "end")):
                local_name = element.tag.rsplit("}", 1)[-1]
                if event == "start" and root_element is None:
                    root_element = local_name
                if event == "end" and local_name == "Firm":
                    firm_count += 1
                    element.clear()
        return {
            "format": "GZIP_XML",
            "root_element": root_element,
            "firm_count": firm_count,
        }
    if source_id in {
        "sec_iapd_homepage_capture_2026_09_24",
        "official_warning_capture_2026_09_24",
    }:
        raw = path.read_bytes()
        prefix = raw[:4096].lower()
        return {
            "format": "HTML",
            "file_size_bytes": len(raw),
            "html_marker_present": b"<html" in prefix or b"<!doctype html" in prefix,
            "utf8_replacement_character_count": raw.decode("utf-8", errors="replace").count("\ufffd"),
        }
    if source_id == "wayback_confirmed_capture_2026_09_24":
        raw = path.read_bytes()
        is_gzip = raw.startswith(b"\x1f\x8b")
        decoded = gzip.decompress(raw) if is_gzip else raw
        prefix = decoded[:4096].lower()
        return {
            "format": "GZIP_HTML" if is_gzip else "HTML",
            "file_size_bytes": len(raw),
            "decoded_size_bytes": len(decoded),
            "html_marker_present": b"<html" in prefix or b"<!doctype html" in prefix,
        }
    raise ValueError(f"Unsupported source_id: {source_id}")


def verify_manifest(manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_id = manifest["source_id"]
    if source_id not in SUPPORTED_SOURCE_IDS:
        raise ValueError(f"Unsupported manifest: {manifest_path.name}")
    raw_path = Path(manifest["storage_path"])
    if not raw_path.is_file():
        return {
            "manifest": manifest_path.name,
            "source_id": source_id,
            "raw_path": str(raw_path),
            "exists": False,
            "sha256_matches_manifest": False,
        }
    observed = sha256_file(raw_path)
    return {
        "manifest": manifest_path.name,
        "source_id": source_id,
        "source_url": manifest["source_url"],
        "source_version": manifest.get("source_version"),
        "raw_path": str(raw_path),
        "exists": True,
        "file_size_bytes": raw_path.stat().st_size,
        "sha256_expected": manifest["raw_file_sha256"],
        "sha256_observed": observed,
        "sha256_matches_manifest": observed == manifest["raw_file_sha256"],
        "structure": compact_profile(source_id, raw_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, action="append", help="Manifest path; repeatable")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    manifests = args.manifest or sorted(MANIFEST_ROOT.glob("*.json"))
    reports = []
    for manifest in manifests:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("source_id") in SUPPORTED_SOURCE_IDS:
            reports.append(verify_manifest(manifest))
    if not reports:
        raise ValueError("No supported raw-data manifests found")
    result = {"verification_mode": "read_only_no_network", "sources": reports}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    if not all(item["sha256_matches_manifest"] for item in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
