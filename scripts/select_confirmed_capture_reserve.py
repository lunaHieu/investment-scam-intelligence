"""Create an offline, unlabeled high-affinity IOSCO confirmed reserve queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.select_external_text_capture_candidates import _load_frozen_index
from scripts.select_sec_legitimate_capture_reserve import _load_primary_queue
from src.isi.curation.external_text_capture_queue import select_confirmed_reserve_candidates
from src.isi.matching.external_domain_references import write_jsonl
from src.isi.normalization.external_references import sha256_file


DEFAULT_IOSCO_REGISTRY = ROOT / "registry" / "analyses" / "iosco_warning_reference_index_v1.json"
DEFAULT_PRIMARY_REGISTRY = ROOT / "registry" / "pilots" / "external_text_capture_candidate_queue_v1.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iosco-registry", type=Path, default=DEFAULT_IOSCO_REGISTRY)
    parser.add_argument("--primary-registry", type=Path, default=DEFAULT_PRIMARY_REGISTRY)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reserve-size", type=int, default=40)
    parser.add_argument("--seed", default="20260924-confirmed")
    parser.add_argument("--candidate-prefix", default="EXTCAP_RESERVE_CONF")
    parser.add_argument("--exclude-registry", type=Path, action="append", default=[])
    args = parser.parse_args()
    existing = [str(path) for path in (args.queue_output, args.report) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen outputs: {existing}")

    iosco_records, iosco_input = _load_frozen_index(args.iosco_registry)
    primary_queue, primary_input = _load_primary_queue(args.primary_registry)
    primary_hosts = {
        str(item.get("candidate_host")).casefold().rstrip(".")
        for item in primary_queue
        if item.get("candidate_host")
    }
    extra_inputs = []
    for registry_path in args.exclude_registry:
        value = json.loads(registry_path.read_text(encoding="utf-8"))
        output_map = {item.get("role"): item for item in value.get("outputs", [])}
        info = output_map.get("capture_candidate_queue") or output_map.get("confirmed_reserve_queue")
        if not isinstance(info, dict):
            raise ValueError(f"No supported queue output in {registry_path}")
        queue_path = Path(str(info.get("path", "")))
        if sha256_file(queue_path) != info.get("sha256"):
            raise ValueError(f"Excluded queue hash mismatch: {queue_path}")
        extra_queue = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines() if line]
        primary_hosts.update(
            str(item.get("candidate_host")).casefold().rstrip(".")
            for item in extra_queue
            if item.get("candidate_host")
        )
        extra_inputs.append({"registry": str(registry_path), **info})
    queue, selection = select_confirmed_reserve_candidates(
        iosco_records,
        primary_hosts,
        reserve_size=args.reserve_size,
        seed=args.seed,
        candidate_id_prefix=args.candidate_prefix,
    )
    write_jsonl(args.queue_output, queue)
    report = {
        "analysis_id": "IOSCO_CONFIRMED_CAPTURE_RESERVE_V1",
        "status": "FROZEN_OFFLINE_RESERVE_QUEUE_CAPTURE_REQUIRED_NOT_LABELED",
        "inputs": {
            "iosco": iosco_input,
            "primary_capture_queue": primary_input,
            "additional_excluded_queues": extra_inputs,
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
    print(json.dumps({**report, "report_sha256": sha256_file(args.report)}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
