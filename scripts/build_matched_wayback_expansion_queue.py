"""Build a hash-pinned acquisition queue for a class-matched Wayback benchmark."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for value in (ROOT, SCRIPTS):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from validate_external_text_intake import sha256_file


WAYBACK_URL = re.compile(r"^https://web\.archive\.org/web/(\d{14})id_/(https?://.+)$")


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def host_from_url(value: str) -> str:
    match = WAYBACK_URL.match(value)
    if match:
        value = match.group(2)
    host = (urlparse(value).hostname or "").casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or any(character.isspace() for character in host):
        raise ValueError(f"Invalid candidate URL: {value}")
    return host


def sec_index_by_record(path: Path) -> dict[str, dict[str, object]]:
    records = load_jsonl(path)
    output = {}
    for record in records:
        record_id = str(record.get("source_record_id", ""))
        if record_id:
            output[record_id] = record
    return output


def build_queue(
    intake: dict[str, object],
    sec_index: dict[str, dict[str, object]],
    raw_root: Path,
) -> list[dict[str, object]]:
    queue = []
    for record in sorted(intake.get("records", []), key=lambda item: item["case_id"]):
        if (
            record.get("review_status") != "RECONCILED"
            or record.get("label_confidence") != "HIGH"
            or record.get("ground_truth_status") not in {"CONFIRMED", "LEGITIMATE"}
        ):
            raise ValueError(f"Record is not a frozen reconciled reference: {record.get('case_id')}")
        artifact = record["artifact"]
        status = record["ground_truth_status"]
        host = host_from_url(str(artifact["url"]))
        evidence = list(record.get("evidence", []))
        if not evidence or not all(item.get("reviewed") is True for item in evidence):
            raise ValueError(f"Reference evidence is incomplete: {record['case_id']}")
        common = {
            "candidate_id": f"MATCHWB_{record['case_id']}",
            "source_case_id": record["case_id"],
            "reference_status": status,
            "reference_status_is_reviewer_visible": False,
            "candidate_host": host,
            "source_record_id": str(artifact["source_record_id"]),
            "target_timestamp": str(artifact["collection_date"]).replace("-", ""),
            "first_review_and_model_outputs_allowed_in_second_review_packet": False,
            "reference_evidence": [
                {
                    "evidence_type": item.get("evidence_type"),
                    "source_id": item.get("source_id"),
                    "source_url": item.get("source_url"),
                    "supports": item.get("supports", []),
                }
                for item in evidence
            ],
        }
        if status == "CONFIRMED":
            match = WAYBACK_URL.match(str(artifact["url"]))
            if not match:
                raise ValueError(f"Confirmed reference is not a Wayback raw replay: {record['case_id']}")
            capture_path = raw_root / str(artifact["source_capture_path"])
            if not capture_path.is_file() or sha256_file(capture_path) != artifact["source_capture_sha256"]:
                raise ValueError(f"Confirmed capture missing or changed: {record['case_id']}")
            common.update(
                {
                    "archive_acquisition_state": "REUSE_HASH_PINNED_CAPTURE",
                    "entity_name_keys": [],
                    "existing_capture": {
                        "path": str(capture_path),
                        "sha256": artifact["source_capture_sha256"],
                        "snapshot_timestamp": match.group(1),
                        "archive_url": artifact["url"],
                        "text_sha256": artifact["text_sha256"],
                    },
                }
            )
        else:
            sec_record = sec_index.get(str(artifact["source_record_id"]))
            if sec_record is None:
                raise ValueError(f"SEC/IAPD reference record is missing: {record['case_id']}")
            observed_hosts = {str(value).casefold().removeprefix("www.") for value in sec_record["observed_hosts"]}
            if host not in observed_hosts:
                raise ValueError(f"Reconciled host does not match the SEC-filed host: {record['case_id']}")
            common.update(
                {
                    "archive_acquisition_state": "NEEDS_ARCHIVE_QUERY",
                    "entity_name_keys": list(sec_record["entity_name_keys"]),
                    "sec_reference": {
                        "sec_number": sec_record.get("sec_number"),
                        "registration": sec_record.get("registration"),
                        "filing": sec_record.get("filing"),
                        "reference_semantics": sec_record.get("reference_semantics"),
                    },
                    "existing_capture": None,
                }
            )
        queue.append(common)
    counts = {status: sum(item["reference_status"] == status for item in queue) for status in ("CONFIRMED", "LEGITIMATE")}
    if counts != {"CONFIRMED": 10, "LEGITIMATE": 11}:
        raise ValueError(f"Unexpected reconciled-pilot class counts: {counts}")
    return queue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument("--intake-sha256", required=True)
    parser.add_argument("--sec-index", type=Path, required=True)
    parser.add_argument("--sec-index-sha256", required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.report):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    if sha256_file(args.intake) != args.intake_sha256:
        raise ValueError("Reconciled intake SHA-256 mismatch")
    if sha256_file(args.sec_index) != args.sec_index_sha256:
        raise ValueError("SEC/IAPD index SHA-256 mismatch")
    queue = build_queue(load_json(args.intake), sec_index_by_record(args.sec_index), args.raw_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for item in queue:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    report = {
        "queue_id": "EXTERNAL_TEXT_MATCHED_WAYBACK_EXPANSION_QUEUE_V1",
        "status": "ACQUISITION_REQUIRED_NO_NEW_LABELS",
        "inputs": {
            "reconciled_intake": {"path": str(args.intake), "sha256": args.intake_sha256},
            "sec_reference_index": {"path": str(args.sec_index), "sha256": args.sec_index_sha256},
        },
        "counts": {
            "candidate_count": len(queue),
            "confirmed_reused_capture_count": sum(item["reference_status"] == "CONFIRMED" for item in queue),
            "legitimate_archive_query_count": sum(item["reference_status"] == "LEGITIMATE" for item in queue),
        },
        "output": {"path": str(args.output), "sha256": sha256_file(args.output)},
        "safety_contract": {
            "network_operations": 0,
            "candidate_live_domain_access_operations": 0,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
