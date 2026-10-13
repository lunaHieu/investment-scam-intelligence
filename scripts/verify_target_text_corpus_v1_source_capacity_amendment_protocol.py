"""Verify the frozen source-capacity amendment protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_SOURCE_CAPACITY_AMENDMENT_PROTOCOL_V1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def verify(protocol_path: Path) -> dict[str, Any]:
    protocol = load_object(protocol_path)
    if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        raise ValueError("Unexpected capacity-amendment protocol ID")
    root = protocol_path.resolve().parents[1]
    for item in protocol.get("basis", []):
        path = Path(str(item.get("path")))
        if not path.is_absolute():
            path = root / path
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Missing or changed protocol basis: {item.get('role')}")

    sec = protocol["sec_edgar_bulk"]
    parsed = urlparse(sec["official_bulk_url"])
    if parsed.scheme != "https" or parsed.hostname != "www.sec.gov":
        raise ValueError("SEC bulk URL is not pinned to official HTTPS host")
    if parsed.path != "/Archives/edgar/daily-index/bulkdata/submissions.zip":
        raise ValueError("Unexpected SEC bulk path")
    request = sec["request_contract"]
    if request["truthful_private_user_agent_required"] is not True:
        raise ValueError("SEC private identity requirement removed")
    if request["private_identity_contents_or_hash_publication_allowed"] is not False:
        raise ValueError("SEC private identity disclosure gate opened")
    if request["maximum_bulk_requests_in_run"] != 1 or request["project_requests_per_second_maximum"] > 1:
        raise ValueError("SEC request budget changed")
    if sec["automatic_ground_truth_allowed"] or sec["candidate_enumeration_allowed_by_this_protocol"]:
        raise ValueError("SEC protocol opened a label or enumeration gate")

    dfpi = protocol["dfpi_tracker"]
    if dfpi["automated_table_or_case_page_scraping_allowed"] is not False:
        raise ValueError("DFPI automated scraping was authorized")
    if dfpi["independent_official_corroboration_required"] is not True:
        raise ValueError("DFPI corroboration requirement removed")
    if dfpi["automatic_confirmed_label_allowed"] is not False:
        raise ValueError("DFPI complaint was converted into an automatic label")

    vietnam = protocol["vietnam_official_issuer_references"]
    if not str(vietnam["access_status"]).startswith("BLOCKED_"):
        raise ValueError("Vietnamese reference channel was opened prematurely")
    if any(
        vietnam[key] is not False
        for key in (
            "automated_collection_allowed",
            "manual_internal_reference_capture_allowed_by_this_protocol",
            "redistribution_allowed_by_this_protocol",
            "automatic_legitimate_label_allowed",
            "candidate_enumeration_allowed_by_this_protocol",
        )
    ):
        raise ValueError("Vietnamese reference or label gate was opened")

    change = protocol["matrix_change_control"]
    if change["sampling_matrix_v1_mutation_allowed"] or change["new_channel_silent_substitution_allowed"]:
        raise ValueError("Sampling-matrix change control was weakened")
    if change["sampling_matrix_v2_required_if_dfpi_or_vietnam_channel_is_adopted"] is not True:
        raise ValueError("Sampling Matrix V2 requirement removed")

    decision = protocol["decision"]
    if decision["sec_bulk_plan_may_be_prepared"] is not True:
        raise ValueError("SEC bulk-plan preparation gate is closed unexpectedly")
    forbidden = (
        "sec_bulk_network_execution_allowed_now",
        "dfpi_network_execution_allowed",
        "vietnam_reference_network_execution_allowed",
        "candidate_enumeration_allowed",
        "capture_allowed",
        "labeling_allowed",
        "training_allowed",
        "model_scoring_allowed",
    )
    if any(decision[key] is not False for key in forbidden):
        raise ValueError("Protocol opened an execution, data, or model gate")

    return {
        "protocol_id": protocol["protocol_id"],
        "sec_bulk_plan_may_be_prepared": decision["sec_bulk_plan_may_be_prepared"],
        "sec_bulk_network_execution_allowed_now": decision["sec_bulk_network_execution_allowed_now"],
        "dfpi_status": dfpi["access_status"],
        "vietnam_status": vietnam["access_status"],
        "candidate_enumeration_allowed": decision["candidate_enumeration_allowed"],
        "training_allowed": decision["training_allowed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
