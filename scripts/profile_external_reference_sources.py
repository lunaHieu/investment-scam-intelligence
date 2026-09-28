"""Create read-only structural profiles for IOSCO I-SCAN and SEC IAPD raw files.

The profiler performs no network operations, creates no labels, and never emits
record-level entity names or narratives. It is intended to run only after both
raw files have been pinned by immutable manifests.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IOSCO_MANIFEST = ROOT / "registry" / "manifests" / "iosco_i_scan__export__2026-09-23.json"
DEFAULT_SEC_MANIFEST = (
    ROOT
    / "registry"
    / "manifests"
    / "sec_iapd__ia_firm_sec_feed_2026-09-22__2026-09-23.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def valid_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def top(counter: Counter[str], limit: int = 20) -> list[dict[str, object]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def profile_iosco(path: Path) -> dict[str, object]:
    expected_columns: list[str] | None = None
    missing: Counter[str] = Counter()
    regulators: Counter[str] = Counter()
    jurisdictions: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    ids: Counter[str] = Counter()
    validation_dates: list[str] = []
    modification_dates: list[str] = []
    invalid_date_counts = Counter()
    replacement_character_count = 0
    rows_with_replacement_character = 0
    replacement_characters_by_column: Counter[str] = Counter()
    presence_fields = [
        "url",
        "other_urls",
        "domain_name",
        "fqdn",
        "email",
        "social_media",
        "regulator_claims",
        "additional_information",
    ]
    presence = Counter()
    row_count = 0

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        expected_columns = list(reader.fieldnames or [])
        for row in reader:
            row_count += 1
            row_replacement_count = 0
            for column in expected_columns:
                value = row.get(column) or ""
                if not value.strip():
                    missing[column] += 1
                replacements = value.count("\ufffd")
                if replacements:
                    replacement_character_count += replacements
                    row_replacement_count += replacements
                    replacement_characters_by_column[column] += replacements
            if row_replacement_count:
                rows_with_replacement_character += 1
            record_id = (row.get("id") or "").strip()
            if record_id:
                ids[record_id] += 1
            regulators[(row.get("nca_name") or "").strip() or "<missing>"] += 1
            jurisdictions[(row.get("nca_jurisdiction") or "").strip() or "<missing>"] += 1
            categories[(row.get("categories_detailed") or "").strip() or "<missing>"] += 1
            for field in presence_fields:
                if (row.get(field) or "").strip():
                    presence[field] += 1
            for field, values in (
                ("validation_date", validation_dates),
                ("modification_date", modification_dates),
            ):
                value = (row.get(field) or "").strip()
                if not value:
                    continue
                if valid_iso_date(value):
                    values.append(value)
                else:
                    invalid_date_counts[field] += 1

    return {
        "source_id": "iosco_i_scan",
        "format": "CSV",
        "row_count": row_count,
        "column_count": len(expected_columns or []),
        "columns": expected_columns or [],
        "duplicate_nonempty_id_count": sum(count - 1 for count in ids.values() if count > 1),
        "encoding_anomalies": {
            "unicode_replacement_character_count": replacement_character_count,
            "rows_with_unicode_replacement_character": rows_with_replacement_character,
            "replacement_characters_by_column": dict(sorted(replacement_characters_by_column.items())),
        },
        "missing_by_column": dict(sorted(missing.items())),
        "nonempty_selected_fields": {field: presence[field] for field in presence_fields},
        "date_ranges": {
            "validation_date": {
                "min": min(validation_dates) if validation_dates else None,
                "max": max(validation_dates) if validation_dates else None,
                "invalid_count": invalid_date_counts["validation_date"],
            },
            "modification_date": {
                "min": min(modification_dates) if modification_dates else None,
                "max": max(modification_dates) if modification_dates else None,
                "invalid_count": invalid_date_counts["modification_date"],
            },
        },
        "top_regulators": top(regulators),
        "top_jurisdictions": top(jurisdictions),
        "top_categories": top(categories),
        "interpretation": "Warning-registry evidence only; not conviction labels and not direct model-input text.",
    }


def profile_sec(path: Path) -> dict[str, object]:
    firm_count = 0
    crd_numbers: Counter[str] = Counter()
    firm_types: Counter[str] = Counter()
    registration_states: Counter[str] = Counter()
    office_states: Counter[str] = Counter()
    office_countries: Counter[str] = Counter()
    filing_versions: Counter[str] = Counter()
    registration_dates: list[str] = []
    invalid_registration_dates = 0
    required_presence = Counter()
    firms_with_web_address = 0
    total_web_addresses = 0

    with gzip.open(path, "rb") as file:
        for event, firm in ET.iterparse(file, events=("end",)):
            if local_name(firm.tag) != "Firm":
                continue
            firm_count += 1
            descendants = {local_name(element.tag): element for element in firm.iter()}
            info = descendants.get("Info")
            registration = descendants.get("Rgstn")
            main_address = descendants.get("MainAddr")
            filing = descendants.get("Filing")
            web_addresses = [
                (element.text or "").strip()
                for element in firm.iter()
                if local_name(element.tag) == "WebAddr" and (element.text or "").strip()
            ]
            total_web_addresses += len(web_addresses)
            if web_addresses:
                firms_with_web_address += 1

            if info is not None:
                crd = (info.attrib.get("FirmCrdNb") or "").strip()
                if crd:
                    crd_numbers[crd] += 1
                    required_presence["FirmCrdNb"] += 1
                for attribute in ("SECNb", "BusNm", "LegalNm"):
                    if (info.attrib.get(attribute) or "").strip():
                        required_presence[attribute] += 1
            if registration is not None:
                firm_types[(registration.attrib.get("FirmType") or "").strip() or "<missing>"] += 1
                registration_states[(registration.attrib.get("St") or "").strip() or "<missing>"] += 1
                date = (registration.attrib.get("Dt") or "").strip()
                if date:
                    if valid_iso_date(date):
                        registration_dates.append(date)
                    else:
                        invalid_registration_dates += 1
            if main_address is not None:
                office_states[(main_address.attrib.get("State") or "").strip() or "<missing>"] += 1
                office_countries[(main_address.attrib.get("Cntry") or "").strip() or "<missing>"] += 1
            if filing is not None:
                filing_versions[(filing.attrib.get("FormVrsn") or "").strip() or "<missing>"] += 1
            firm.clear()

    return {
        "source_id": "sec_iapd",
        "format": "GZIP_XML",
        "firm_count": firm_count,
        "duplicate_nonempty_crd_count": sum(count - 1 for count in crd_numbers.values() if count > 1),
        "required_attribute_nonempty_counts": dict(sorted(required_presence.items())),
        "firms_with_web_address": firms_with_web_address,
        "total_nonempty_web_addresses": total_web_addresses,
        "registration_date": {
            "min": min(registration_dates) if registration_dates else None,
            "max": max(registration_dates) if registration_dates else None,
            "invalid_count": invalid_registration_dates,
        },
        "firm_types": top(firm_types),
        "registration_states": top(registration_states),
        "top_office_states": top(office_states),
        "top_office_countries": top(office_countries),
        "filing_versions": top(filing_versions),
        "interpretation": "Official registration reference only; not a content-safety label and not proof against impersonation.",
    }


def load_verified_manifest(path: Path, expected_source_id: str) -> tuple[dict[str, object], Path]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("source_id") != expected_source_id:
        raise ValueError(f"Expected {expected_source_id} manifest: {path}")
    raw_path = Path(str(manifest["storage_path"]))
    if not raw_path.is_file():
        raise FileNotFoundError(raw_path)
    observed = sha256_file(raw_path)
    if observed != manifest.get("raw_file_sha256"):
        raise ValueError(f"Raw hash does not match manifest: {raw_path}")
    return manifest, raw_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iosco-manifest", type=Path, default=DEFAULT_IOSCO_MANIFEST)
    parser.add_argument("--sec-manifest", type=Path, default=DEFAULT_SEC_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    iosco_manifest, iosco_path = load_verified_manifest(args.iosco_manifest, "iosco_i_scan")
    sec_manifest, sec_path = load_verified_manifest(args.sec_manifest, "sec_iapd")
    result = {
        "profile_version": "V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifests": {
            "iosco": args.iosco_manifest.as_posix(),
            "sec": args.sec_manifest.as_posix(),
        },
        "raw_sha256": {
            "iosco": iosco_manifest["raw_file_sha256"],
            "sec": sec_manifest["raw_file_sha256"],
        },
        "profiles": {
            "iosco": profile_iosco(iosco_path),
            "sec": profile_sec(sec_path),
        },
        "safety_contract": {
            "network_operations": 0,
            "raw_files_modified": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
