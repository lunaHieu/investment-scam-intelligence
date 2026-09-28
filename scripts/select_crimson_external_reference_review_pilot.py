"""Select and freeze the deterministic Crimson external-reference review pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.crimson_reference_pilot import select_pilot
from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file


DEFAULT_REGISTRY = ROOT / "registry" / "analyses" / "crimson_external_reference_match_v1.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--pilot-output", required=True, type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    existing = [str(path) for path in (args.pilot_output, args.evidence_output, args.report) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen pilot outputs: {existing}")

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    match_info = outputs["reference_matches"]
    queue_info = outputs["review_queue"]
    match_path = Path(str(match_info["path"]))
    queue_path = Path(str(queue_info["path"]))
    for role, path, expected in (
        ("reference_matches", match_path, match_info["sha256"]),
        ("review_queue", queue_path, queue_info["sha256"]),
    ):
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"{role} SHA-256 mismatch: {actual}")

    pilot, evidence, summary = select_pilot(load_jsonl(queue_path), load_jsonl(match_path))
    write_jsonl(args.pilot_output, pilot)
    write_jsonl(args.evidence_output, evidence)
    report = {
        **summary,
        "inputs": {
            "match_registry": str(args.registry),
            "reference_matches_path": str(match_path),
            "reference_matches_sha256": match_info["sha256"],
            "review_queue_path": str(queue_path),
            "review_queue_sha256": queue_info["sha256"],
        },
        "outputs": {
            "pilot_records": {
                "path": str(args.pilot_output),
                "sha256": sha256_file(args.pilot_output),
                "record_count": len(pilot),
            },
            "evidence_records": {
                "path": str(args.evidence_output),
                "sha256": sha256_file(args.evidence_output),
                "record_count": len(evidence),
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
