"""Create a no-label offline Crimson-to-IOSCO/SEC reference match queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import build_match_outputs
from src.isi.normalization.external_references import sha256_file


DEFAULT_CRIMSON_REGISTRY = ROOT / "registry" / "features" / "crimson_url_lexical_v1.json"
DEFAULT_IOSCO_REGISTRY = ROOT / "registry" / "analyses" / "iosco_warning_reference_index_v1.json"
DEFAULT_SEC_REGISTRY = ROOT / "registry" / "analyses" / "sec_iapd_reference_index_v1.json"


def verified_path(path: Path, expected_sha256: str, role: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {role}: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(f"{role} SHA-256 mismatch: expected {expected_sha256}, observed {actual}")
    return path


def reference_index_from_registry(path: Path, source_id: str) -> tuple[Path, str]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("source_id") != source_id:
        raise ValueError(f"Unexpected source registry: {path}")
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    index = outputs.get("reference_index")
    if not index:
        raise ValueError(f"Registry has no reference_index: {path}")
    expected_hash = str(index["sha256"])
    return verified_path(Path(str(index["path"])), expected_hash, source_id), expected_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crimson-registry", type=Path, default=DEFAULT_CRIMSON_REGISTRY)
    parser.add_argument("--iosco-registry", type=Path, default=DEFAULT_IOSCO_REGISTRY)
    parser.add_argument("--sec-registry", type=Path, default=DEFAULT_SEC_REGISTRY)
    parser.add_argument("--matches-output", type=Path, required=True)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    existing = [str(path) for path in (args.matches_output, args.queue_output, args.report) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen outputs: {existing}")

    crimson_registry = json.loads(args.crimson_registry.read_text(encoding="utf-8"))
    lineage = crimson_registry.get("lineage", {})
    crimson_hash = str(lineage["candidate_artifact_sha256"])
    crimson_path = verified_path(
        Path(str(lineage["candidate_artifact_path"])), crimson_hash, "Crimson candidate artifacts"
    )
    iosco_path, iosco_hash = reference_index_from_registry(args.iosco_registry, "iosco_i_scan")
    sec_path, sec_hash = reference_index_from_registry(args.sec_registry, "sec_iapd")
    report = build_match_outputs(
        crimson_path,
        iosco_path,
        sec_path,
        args.matches_output,
        args.queue_output,
        input_hashes={"crimson": crimson_hash, "iosco": iosco_hash, "sec": sec_hash},
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
