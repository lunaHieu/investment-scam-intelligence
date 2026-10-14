"""Audit registered raw-source manifests and report raw-directory coverage offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_raw_data import MANIFEST_ROOT, SUPPORTED_SOURCE_IDS, sha256_file, verify_manifest


RAW_ROOT = Path(r"D:\nckh 2026-2027\ISI_Data\raw")


def supported_manifest_paths(manifest_root: Path = MANIFEST_ROOT) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(manifest_root.glob("*.json"), key=lambda item: item.name):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("source_id") in SUPPORTED_SOURCE_IDS:
            paths.append(path)
    return paths


def manifest_set_sha256(paths: list[Path]) -> str:
    lines = [f"{path.name}\t{sha256_file(path)}" for path in paths]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def raw_inventory(raw_root: Path, covered_paths: set[Path]) -> tuple[list[dict[str, Any]], int, int]:
    directories: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0
    for directory in sorted((item for item in raw_root.iterdir() if item.is_dir()), key=lambda item: item.name):
        files = sorted((item for item in directory.rglob("*") if item.is_file()), key=lambda item: str(item).casefold())
        covered = sum(item.resolve() in covered_paths for item in files)
        byte_count = sum(item.stat().st_size for item in files)
        directories.append(
            {
                "directory": directory.name,
                "file_count": len(files),
                "byte_count": byte_count,
                "source_manifest_covered_files": covered,
                "outside_source_manifest_scope_files": len(files) - covered,
            }
        )
        total_files += len(files)
        total_bytes += byte_count
    return directories, total_files, total_bytes


def build_report(manifest_root: Path = MANIFEST_ROOT, raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    manifests = supported_manifest_paths(manifest_root)
    reports = [verify_manifest(path) for path in manifests]
    covered_paths = {
        Path(item["raw_path"]).resolve()
        for item in reports
        if item.get("exists") is True and is_within(Path(item["raw_path"]), raw_root)
    }
    directories, total_files, total_bytes = raw_inventory(raw_root, covered_paths)
    source_counts = Counter(str(item["source_id"]) for item in reports)
    missing = sum(item.get("exists") is not True for item in reports)
    mismatches = sum(item.get("sha256_matches_manifest") is not True for item in reports)
    structure_failures = sum(
        item.get("structure", {}).get("html_marker_present") is False
        for item in reports
        if "html_marker_present" in item.get("structure", {})
    )
    registered_ok = missing == 0 and mismatches == 0 and structure_failures == 0
    return {
        "audit_id": "ISI_RAW_SOURCE_MANIFEST_COVERAGE_AUDIT_V1",
        "status": "PASS_REGISTERED_MANIFESTS_INTACT_RAW_COVERAGE_PARTIAL" if registered_ok else "FAIL_REGISTERED_MANIFEST_INTEGRITY",
        "verification_mode": "READ_ONLY_NO_NETWORK",
        "manifest_set": {
            "supported_manifest_count": len(manifests),
            "supported_manifest_set_sha256": manifest_set_sha256(manifests),
            "source_counts": dict(sorted(source_counts.items())),
        },
        "registered_integrity": {
            "existing_raw_files": len(reports) - missing,
            "missing_raw_files": missing,
            "hash_matches": len(reports) - mismatches,
            "hash_mismatches": mismatches,
            "html_structure_failures": structure_failures,
        },
        "raw_directory_inventory": {
            "raw_root": str(raw_root),
            "file_count": total_files,
            "byte_count": total_bytes,
            "source_manifest_covered_files": len(covered_paths),
            "outside_source_manifest_scope_files": total_files - len(covered_paths),
            "directories": directories,
            "interpretation": "Files outside the source-manifest scope are not declared corrupt or ungoverned; they require a separate cross-registry provenance-coverage audit.",
        },
        "sources": reports,
        "decision": {
            "registered_source_files_pass_integrity": registered_ok,
            "all_raw_files_provenance_verified": False,
            "next_gate": "Audit every file outside the source-manifest scope against capture, acquisition, and result registries before claiming complete raw provenance coverage.",
            "training_allowed": False,
            "validation_or_test_opening_allowed": False,
            "labeling_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "raw_file_modifications": 0,
            "labels_created": 0,
            "model_operations": 0,
            "validation_or_test_openings": 0,
            "training_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite raw-source manifest coverage audit")
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({key: report[key] for key in ("audit_id", "status", "manifest_set", "registered_integrity", "raw_directory_inventory", "decision")}, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
