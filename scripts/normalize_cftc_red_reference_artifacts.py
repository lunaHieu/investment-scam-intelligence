"""Normalize explicitly retrieved CFTC RED detail pages into unlabeled reference rows."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strip_markup(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def parse_detail(path: Path) -> dict[str, str]:
    value = path.read_text(encoding="utf-8", errors="strict")
    title_match = re.search(
        r'<h1[^>]*class="page-header"[^>]*>.*?RED List:\s*(.*?)</span>',
        value,
        re.IGNORECASE | re.DOTALL,
    )
    address_match = re.search(
        r"<b>Web address:</b>\s*(.*?)</(?:li|liclass)>",
        value,
        re.IGNORECASE | re.DOTALL,
    )
    date_match = re.search(
        r"<b>RED List date:</b>\s*([^<]+)</li>",
        value,
        re.IGNORECASE,
    )
    if not title_match or not address_match or not date_match:
        raise ValueError(f"Required CFTC detail fields missing: {path}")
    entity_name = strip_markup(title_match.group(1))
    web_address = strip_markup(address_match.group(1))
    domains = re.findall(
        r"(?:https?://)?(?:www\.)?([a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,})(?:[/\s,;]|$)",
        web_address.casefold(),
    )
    domains = sorted({domain.rstrip(".") for domain in domains})
    if len(domains) != 1:
        raise ValueError(f"Expected exactly one candidate host in {path}, found {domains}")
    node_match = re.fullmatch(r"detail_(\d+)_\d{4}-\d{2}-\d{2}\.html", path.name)
    if not node_match:
        raise ValueError(f"Unexpected CFTC detail filename: {path.name}")
    return {
        "source_record_id": node_match.group(1),
        "entity_name": entity_name,
        "candidate_host": domains[0],
        "red_list_date": date_match.group(1).strip(),
    }


def write_jsonl(path: Path, records: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail-directory", type=Path, required=True)
    parser.add_argument("--exclusion-index", type=Path, required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.report}")
    exclusion = json.loads(args.exclusion_index.read_text(encoding="utf-8"))
    opened_host_hashes = {
        record["normalized_host_sha256"]
        for record in exclusion.get("records", [])
        if record.get("normalized_host_sha256")
    }
    opened_source_records = {
        str(record["source_record_id"])
        for record in exclusion.get("records", [])
        if record.get("source_record_id")
    }
    records: list[dict] = []
    for path in sorted(args.detail_directory.glob("detail_*_*.html")):
        parsed = parse_detail(path)
        host = parsed["candidate_host"]
        host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
        if host_hash in opened_host_hashes:
            raise ValueError(f"CFTC candidate host overlaps an opened cohort: {host_hash}")
        if parsed["source_record_id"] in opened_source_records:
            raise ValueError(f"CFTC source record ID overlaps an opened cohort: {parsed['source_record_id']}")
        source_url = f"https://www.cftc.gov/REDlist/node/{parsed['source_record_id']}"
        if urlparse(source_url).hostname != "www.cftc.gov":
            raise ValueError("CFTC source host changed")
        records.append(
            {
                "source_id": "cftc_red_list",
                "source_record_id": parsed["source_record_id"],
                "reference_url": source_url,
                "reference_observed_at": args.observed_at,
                "reference_sha256": sha256_file(path),
                "entity_name_from_reference": parsed["entity_name"],
                "candidate_url": f"https://{host}/",
                "normalized_host": host,
                "identity_linkage_basis": "Exact web address printed on the frozen CFTC RED detail page.",
                "opened_normalized_host": "PASS",
                "opened_reference_identity": "PASS",
                "legacy_component": "PASS",
            }
        )
    unique_host_count = len({record["normalized_host"] for record in records})
    if unique_host_count < 10:
        raise ValueError(
            "At least 10 unique CFTC hosts are required after explicit retrieval: "
            f"records={len(records)}, unique_hosts={unique_host_count}"
        )
    write_jsonl(args.output, records)
    report = {
        "analysis_id": "ISI_TARGET_TEXT_CORPUS_V1_CFTC_REFERENCE_NORMALIZATION_V1",
        "status": "FROZEN_REFERENCE_ROWS_UNLABELED_NOT_CAPTURED",
        "input_directory": str(args.detail_directory),
        "input_detail_count": len(records),
        "exclusion_index": {
            "path": str(args.exclusion_index),
            "sha256": sha256_file(args.exclusion_index),
        },
        "output": {
            "path": str(args.output),
            "sha256": sha256_file(args.output),
            "record_count": len(records),
        },
        "quality": {
            "unique_source_record_ids": len({record["source_record_id"] for record in records}),
            "unique_normalized_hosts": unique_host_count,
            "duplicate_host_reference_rows": len(records) - unique_host_count,
            "opened_host_overlaps": 0,
            "opened_source_record_overlaps": 0,
        },
        "safety_contract": {
            "candidate_domain_access_operations": 0,
            "artifact_captures": 0,
            "labels_created": 0,
            "model_operations": 0,
            "training_allowed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
