"""Ingest a manually downloaded, commit-pinned Crimson data.json file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.collection.crimson import ingest_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Pinned Crimson data.json")
    parser.add_argument("--commit", required=True, help="Full 40-character repository commit SHA")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--manifest-root", type=Path, default=ROOT / "registry" / "manifests")
    parser.add_argument("--report-root", type=Path, default=ROOT / "data" / "interim" / "profiles")
    args = parser.parse_args()
    raw, manifest, report = ingest_json(
        args.input, args.raw_root, args.manifest_root, args.report_root, args.commit
    )
    print(f"Raw: {raw}")
    print(f"Manifest: {manifest}")
    print(f"Profile: {report}")


if __name__ == "__main__":
    main()
