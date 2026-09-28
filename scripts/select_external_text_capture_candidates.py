"""Create a balanced, unlabeled external-text capture candidate queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.curation.external_text_capture_queue import select_capture_candidates
from src.isi.matching.external_domain_references import load_jsonl, write_jsonl
from src.isi.normalization.external_references import sha256_file


DEFAULT_IOSCO_REGISTRY = ROOT / "registry" / "analyses" / "iosco_warning_reference_index_v1.json"
DEFAULT_SEC_REGISTRY = ROOT / "registry" / "analyses" / "sec_iapd_reference_index_v1.json"


def _load_frozen_index(registry_path: Path, role: str = "reference_index") -> tuple[list[dict], dict]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    outputs = {item.get("role"): item for item in registry.get("outputs", [])}
    info = outputs.get(role)
    if not isinstance(info, dict):
        raise ValueError(f"Missing {role} in {registry_path}")
    path = Path(str(info.get("path")))
    actual = sha256_file(path)
    if actual != info.get("sha256"):
        raise ValueError(f"Frozen index hash mismatch for {path}: {actual}")
    records = load_jsonl(path)
    if len(records) != info.get("record_count"):
        raise ValueError(f"Frozen index record count mismatch for {path}")
    return records, {"registry": str(registry_path), **info}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iosco-registry", type=Path, default=DEFAULT_IOSCO_REGISTRY)
    parser.add_argument("--sec-registry", type=Path, default=DEFAULT_SEC_REGISTRY)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--per-target", type=int, default=15)
    parser.add_argument("--seed", default="20260923")
    args = parser.parse_args()

    existing = [str(path) for path in (args.queue_output, args.report) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite frozen outputs: {existing}")

    iosco_records, iosco_input = _load_frozen_index(args.iosco_registry)
    sec_records, sec_input = _load_frozen_index(args.sec_registry)
    queue, report = select_capture_candidates(
        iosco_records,
        sec_records,
        per_target=args.per_target,
        seed=args.seed,
    )
    write_jsonl(args.queue_output, queue)
    report = {
        "analysis_id": "EXTERNAL_TEXT_CAPTURE_CANDIDATE_QUEUE_V1",
        "status": "FROZEN_CANDIDATE_QUEUE_CAPTURE_REQUIRED_NOT_LABELED",
        "inputs": {"iosco": iosco_input, "sec_iapd": sec_input},
        **report,
        "output": {
            "path": str(args.queue_output),
            "sha256": sha256_file(args.queue_output),
            "record_count": len(queue),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_sha256"] = sha256_file(args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
