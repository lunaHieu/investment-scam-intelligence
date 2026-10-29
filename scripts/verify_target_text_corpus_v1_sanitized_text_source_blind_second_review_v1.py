"""Verify the blind source-review packet and, when present, its response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "configs" / "target_text_corpus_v1_sanitized_text_source_blind_second_review_packet_v1.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_packet(path: Path = PACKET) -> dict:
    value = load(path)
    blind = value["blindness_contract"]
    if any((blind["primary_dispositions_included"], blind["primary_risks_included"], blind["primary_ranking_included"])):
        raise ValueError("Primary review information leaked into blind packet")
    ids = [item["candidate_id"] for item in value["candidates"]]
    if ids != [f"DISC_V1_{index:03d}" for index in range(1, 7)]:
        raise ValueError("Blind candidate identity/order mismatch")
    if len({item["landing_url"] for item in value["candidates"]}) != 6:
        raise ValueError("Candidate landing URLs are not unique")
    decision = value["decision"]
    for key in ("acquisition_allowed", "candidate_live_domain_access_allowed", "labeling_allowed", "training_allowed"):
        if decision[key] is not False:
            raise ValueError(f"Safety gate opened: {key}")
    return {"status":"PASS_BLIND_PACKET_VERIFIED","candidate_count":6}


def verify_response(response_path: Path, packet_path: Path = PACKET) -> dict:
    packet = load(packet_path)
    response = load(response_path)
    expected_ids = [item["candidate_id"] for item in packet["candidates"]]
    rows = response["reviews"]
    if [row["candidate_id"] for row in rows] != expected_ids:
        raise ValueError("Response candidate identity/order mismatch")
    required = set(packet["response_contract"]["required_fields"])
    allowed_verdicts = set(packet["review_contract"]["verdicts"])
    required_checks = set(packet["review_contract"]["required_checks"])
    for row in rows:
        if set(row) != required:
            raise ValueError(f"Response schema mismatch: {row.get('candidate_id')}")
        if row["verdict"] not in allowed_verdicts:
            raise ValueError(f"Invalid verdict: {row['candidate_id']}")
        if set(row["checks"]) != required_checks:
            raise ValueError(f"Check coverage mismatch: {row['candidate_id']}")
    safety = response["safety_contract"]
    for key in ("dataset_downloads", "candidate_domain_access_operations", "raw_html_files_retained", "labels_created", "model_operations"):
        if safety[key] != 0:
            raise ValueError(f"Forbidden review operation: {key}")
    if response["decision"]["acquisition_allowed"] is not False or response["decision"]["training_allowed"] is not False:
        raise ValueError("Response opened acquisition or training")
    return {"status":"PASS_BLIND_RESPONSE_VERIFIED","candidate_count":len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", type=Path)
    args = parser.parse_args()
    result = verify_response(args.response) if args.response else verify_packet()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
