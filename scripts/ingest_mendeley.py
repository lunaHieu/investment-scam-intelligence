"""Ingest an already-downloaded Mendeley V2 CSV without network access."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.collection.mendeley import ingest_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to the downloaded Mendeley V2 CSV")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--manifest-root", type=Path, default=Path("registry/manifests"))
    parser.add_argument("--report-root", type=Path, default=Path("reports/data"))
    args = parser.parse_args()
    raw, manifest, report = ingest_csv(args.input, args.raw_root, args.manifest_root, args.report_root)
    print(f"Raw file: {raw}")
    print(f"Manifest: {manifest}")
    print(f"Profile report: {report}")


if __name__ == "__main__":
    main()
