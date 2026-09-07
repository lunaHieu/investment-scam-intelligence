"""Validate registry and data-contract files without external dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    registry = load_json(ROOT / "registry" / "sources.json")
    assert isinstance(registry, dict)
    sources = registry["sources"]
    source_ids = [source["source_id"] for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate source_id in registry/sources.json")
    for source in sources:
        if not urlparse(source["url"]).scheme:
            raise ValueError(f"Invalid URL for {source['source_id']}")
        if source["default_evidence_level"] == "SYNTHETIC_ONLY" and source["gold_eligible"]:
            raise ValueError(f"Synthetic source cannot be Gold eligible: {source['source_id']}")
    taxonomy = load_json(ROOT / "registry" / "taxonomy.json")
    codes = [item["code"] for item in taxonomy["subtypes"]]
    if len(codes) != 7 or len(codes) != len(set(codes)):
        raise ValueError("Taxonomy V1 must contain exactly seven unique primary subtypes")
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        schema = load_json(path)
        if not isinstance(schema, dict) or not schema.get("required"):
            raise ValueError(f"Schema must declare required fields: {path.name}")
    readiness = ROOT / "registry" / "source_readiness.md"
    if not readiness.is_file():
        raise ValueError("Missing source readiness audit")
    print(f"Registry valid: {len(sources)} sources, {len(codes)} taxonomy subtypes, schemas checked.")


if __name__ == "__main__":
    main()
