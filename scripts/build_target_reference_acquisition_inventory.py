"""Inventory explicitly acquired CFTC and SEC reference artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path, role: str) -> dict:
    return {
        "role": role,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cftc-directory", type=Path, required=True)
    parser.add_argument("--sec-directory", type=Path, required=True)
    parser.add_argument("--sec-submissions-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    cftc_list_pages = sorted(args.cftc_directory.glob("cftc_red_list*_2026-10-03.html"))
    cftc_details = sorted(args.cftc_directory.glob("detail_*_2026-10-03.html"))
    sec_tickers = sorted(args.sec_directory.glob("company_tickers_exchange_2026-10-03.json*"))
    sec_submissions = sorted(args.sec_submissions_directory.glob("CIK*.json"))
    if len(cftc_list_pages) != 2 or len(cftc_details) != 15:
        raise ValueError("Expected 2 CFTC list pages and 15 explicitly selected detail pages")
    if len(sec_tickers) != 2 or len(sec_submissions) != 20:
        raise ValueError("Expected 2 SEC ticker transfers and 20 submission files")
    inventory = {
        "inventory_id": "ISI_TARGET_TEXT_CORPUS_V1_REFERENCE_ACQUISITION_INVENTORY_V1",
        "created_at": "2026-10-03T07:45:00+07:00",
        "status": "FROZEN_OFFICIAL_REFERENCE_ACQUISITION_COMPLETE",
        "cftc": {
            "acquisition_mode": "USER_AUTHORIZED_EXACT_OFFICIAL_PAGE_RETRIEVAL",
            "official_host": "www.cftc.gov",
            "network_request_count": len(cftc_list_pages) + len(cftc_details),
            "list_pages": [artifact(path, "red_list_page") for path in cftc_list_pages],
            "detail_pages": [artifact(path, "red_list_detail") for path in cftc_details],
        },
        "sec": {
            "acquisition_mode": "DOCUMENTED_OFFICIAL_FILE_AND_SUBMISSIONS_API",
            "official_hosts": ["www.sec.gov", "data.sec.gov"],
            "network_request_count": len(sec_tickers) + len(sec_submissions),
            "project_requests_per_second_maximum": 1,
            "private_contact_identity_disclosed": False,
            "private_identity_sha256_disclosed": False,
            "ticker_artifacts": [artifact(path, "company_tickers_exchange") for path in sec_tickers],
            "submission_artifacts": [artifact(path, "company_submission") for path in sec_submissions],
        },
        "safety_contract": {
            "candidate_domain_access_operations": 0,
            "candidate_artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "cftc_network_requests": inventory["cftc"]["network_request_count"],
                "sec_network_requests": inventory["sec"]["network_request_count"],
                "candidate_domain_access_operations": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
