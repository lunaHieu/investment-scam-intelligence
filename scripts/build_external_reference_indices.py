"""Build no-label, offline lookup indices from pinned IOSCO and SEC raw files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import (
    INDEX_SCHEMA_VERSION,
    build_iosco_index,
    build_sec_index,
    sha256_file,
)


DEFAULT_IOSCO_MANIFEST = ROOT / "registry" / "manifests" / "iosco_i_scan__export__2026-09-23.json"
DEFAULT_SEC_MANIFEST = (
    ROOT / "registry" / "manifests" / "sec_iapd__ia_firm_sec_feed_2026-09-22__2026-09-23.json"
)


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


def ensure_outputs_do_not_exist(paths: list[Path]) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen outputs: {existing}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iosco-manifest", type=Path, default=DEFAULT_IOSCO_MANIFEST)
    parser.add_argument("--sec-manifest", type=Path, default=DEFAULT_SEC_MANIFEST)
    parser.add_argument("--iosco-output", type=Path, required=True)
    parser.add_argument("--sec-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    ensure_outputs_do_not_exist([args.iosco_output, args.sec_output, args.report])

    iosco_manifest, iosco_raw = load_verified_manifest(args.iosco_manifest, "iosco_i_scan")
    sec_manifest, sec_raw = load_verified_manifest(args.sec_manifest, "sec_iapd")
    iosco = build_iosco_index(
        iosco_raw,
        args.iosco_output,
        source_version=str(iosco_manifest["source_version"]),
        raw_sha256=str(iosco_manifest["raw_file_sha256"]),
    )
    sec = build_sec_index(
        sec_raw,
        args.sec_output,
        source_version=str(sec_manifest["source_version"]),
        raw_sha256=str(sec_manifest["raw_file_sha256"]),
    )
    report = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "status": "FROZEN_OFFLINE_REFERENCE_INDICES_NOT_LABELS",
        "inputs": {
            "iosco_manifest": str(args.iosco_manifest),
            "sec_manifest": str(args.sec_manifest),
            "iosco_raw_sha256": iosco_manifest["raw_file_sha256"],
            "sec_raw_sha256": sec_manifest["raw_file_sha256"],
        },
        "indices": {"iosco": iosco, "sec": sec},
        "output_contract": {
            "label_fields": [],
            "free_text_narratives_copied": False,
            "postal_addresses_copied": False,
            "phone_numbers_copied": False,
            "network_operations": 0,
            "model_training_operations": 0,
        },
        "safety_contract": {
            "labels_created": 0,
            "training_allowed": False,
            "domain_access_allowed": False,
            "automatic_entity_resolution_allowed": False,
            "manual_evidence_review_required": True,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
