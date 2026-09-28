"""Create an offline, unlabeled SEC/IAPD reserve capture queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.select_external_text_capture_candidates import _load_frozen_index
from src.isi.curation.external_text_capture_queue import select_legitimate_reserve_candidates
from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file


DEFAULT_IOSCO_REGISTRY = ROOT / "registry" / "analyses" / "iosco_warning_reference_index_v1.json"
DEFAULT_SEC_REGISTRY = ROOT / "registry" / "analyses" / "sec_iapd_reference_index_v1.json"
DEFAULT_PRIMARY_REGISTRY = ROOT / "registry" / "pilots" / "external_text_capture_candidate_queue_v1.json"


def _load_primary_queue(registry_path: Path) -> tuple[list[dict], dict]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    info = outputs.get("capture_candidate_queue")
    if not isinstance(info, dict):
        raise ValueError(f"Missing capture_candidate_queue in {registry_path}")
    path = Path(str(info.get("path")))
    actual_hash = sha256_file(path)
    if actual_hash != info.get("sha256"):
        raise ValueError(f"Primary queue hash mismatch for {path}: {actual_hash}")
    records = load_jsonl(path)
    if len(records) != info.get("record_count"):
        raise ValueError(f"Primary queue record count mismatch for {path}")
    return records, {"registry": str(registry_path), **info}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iosco-registry", type=Path, default=DEFAULT_IOSCO_REGISTRY)
    parser.add_argument("--sec-registry", type=Path, default=DEFAULT_SEC_REGISTRY)
    parser.add_argument("--primary-registry", type=Path, default=DEFAULT_PRIMARY_REGISTRY)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reserve-size", type=int, default=30)
    parser.add_argument("--seed", default="20260924")
    args = parser.parse_args()

    existing_outputs = [str(path) for path in (args.queue_output, args.report) if path.exists()]
    if existing_outputs:
        raise FileExistsError(f"Refusing to overwrite frozen outputs: {existing_outputs}")

    iosco_records, iosco_input = _load_frozen_index(args.iosco_registry)
    sec_records, sec_input = _load_frozen_index(args.sec_registry)
    primary_queue, primary_input = _load_primary_queue(args.primary_registry)
    primary_hosts = {
        str(item.get("candidate_host")).casefold().rstrip(".")
        for item in primary_queue
        if item.get("candidate_host")
    }

    queue, selection = select_legitimate_reserve_candidates(
        iosco_records,
        sec_records,
        primary_hosts,
        reserve_size=args.reserve_size,
        seed=args.seed,
    )
    write_jsonl(args.queue_output, queue)
    report = {
        "analysis_id": "SEC_LEGITIMATE_CAPTURE_RESERVE_V1",
        "status": "FROZEN_OFFLINE_RESERVE_QUEUE_CAPTURE_REQUIRED_NOT_LABELED",
        "inputs": {
            "iosco": iosco_input,
            "sec_iapd": sec_input,
            "primary_capture_queue": primary_input,
        },
        **selection,
        "output": {
            "path": str(args.queue_output),
            "sha256": sha256_file(args.queue_output),
            "record_count": len(queue),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "report_sha256": sha256_file(args.report)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
