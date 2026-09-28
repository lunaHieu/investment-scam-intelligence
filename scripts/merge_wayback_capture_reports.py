"""Merge disjoint Wayback capture reports without changing raw captures."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from validate_external_text_intake import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    results = []
    seen = set()
    input_records = []
    network_requests = 0
    for path in args.input:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("report_id") != "WAYBACK_CONFIRMED_CANDIDATE_CAPTURE_V1":
            raise ValueError(f"Unexpected report ID: {path}")
        safety = report.get("safety_contract", {})
        if safety.get("candidate_domain_access_operations") != 0:
            raise ValueError(f"Unsafe report claims candidate-domain access: {path}")
        input_records.append({"path": str(path), "sha256": sha256_file(path)})
        network_requests += int(report.get("network_request_count", 0))
        for item in report.get("results", []):
            candidate_id = item.get("candidate_id")
            if candidate_id in seen:
                raise ValueError(f"Duplicate candidate across reports: {candidate_id}")
            seen.add(candidate_id)
            results.append(item)

    results.sort(key=lambda item: str(item.get("candidate_id")))
    output = {
        "report_id": "WAYBACK_CONFIRMED_CANDIDATE_CAPTURE_MERGED_V1",
        "created_at": datetime.now().astimezone().isoformat(),
        "inputs": input_records,
        "network_request_count": network_requests,
        "result_count": len(results),
        "captured_count": sum(item.get("outcome") == "CAPTURED" for item in results),
        "failed_count": sum(item.get("outcome") == "FAILED" for item in results),
        "skipped_existing_count": sum(item.get("outcome") == "SKIPPED_EXISTING" for item in results),
        "results": results,
        "safety_contract": {
            "candidate_domain_access_operations": 0,
            "only_web_archive_host_accessed": True,
            "raw_replay_modifier_used": True,
            "automatic_external_redirect_following": False,
            "labels_created": 0,
            "model_scoring_operations": 0,
            "training_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**output, "output_sha256": sha256_file(args.output)}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
