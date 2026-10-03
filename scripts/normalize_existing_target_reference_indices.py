"""Normalize frozen IOSCO and SEC/IAPD indices for Target Text Corpus V1."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


BLOCKED_SHARED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "linktr.ee",
    "medium.com",
    "substack.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def clean_host(record: dict) -> str | None:
    hosts = record.get("observed_hosts")
    if not isinstance(hosts, list) or len(hosts) != 1 or not isinstance(hosts[0], str):
        return None
    host = hosts[0].casefold().rstrip(".")
    if not host or "." not in host or host in BLOCKED_SHARED_HOSTS:
        return None
    return host


def entity_name(record: dict) -> str | None:
    values = record.get("entity_name_keys")
    if not isinstance(values, list):
        return None
    cleaned = sorted({str(value).strip() for value in values if str(value).strip()})
    return cleaned[0] if cleaned else None


def base_row(
    record: dict,
    *,
    source_id: str,
    source_record_id: str,
    reference_url: str,
    reference_sha256: str,
    observed_at: str,
    entity: str,
    host: str,
) -> dict:
    return {
        "source_id": source_id,
        "source_record_id": source_record_id,
        "reference_url": reference_url,
        "reference_observed_at": observed_at,
        "reference_sha256": reference_sha256,
        "entity_name_from_reference": entity,
        "candidate_url": f"https://{host}/",
        "normalized_host": host,
        "identity_linkage_basis": "Exact single host stored with the entity in the frozen official-reference index.",
        "opened_normalized_host": "PASS",
        "opened_reference_identity": "PASS",
        "legacy_component": "PASS",
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iosco-index", type=Path, required=True)
    parser.add_argument("--sec-iapd-index", type=Path, required=True)
    parser.add_argument("--exclusion-index", type=Path, required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--iosco-output", type=Path, required=True)
    parser.add_argument("--sec-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.iosco_output, args.sec_output, args.report):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    iosco_records = load_jsonl(args.iosco_index)
    sec_records = load_jsonl(args.sec_iapd_index)
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
    iosco_index_sha = sha256_file(args.iosco_index)
    sec_index_sha = sha256_file(args.sec_iapd_index)
    counts: Counter[str] = Counter()
    iosco_rows: list[dict] = []
    iosco_hosts: set[str] = set()
    for record in iosco_records:
        host = clean_host(record)
        entity = entity_name(record)
        notice_url = str(record.get("notice_reference_url", ""))
        regulator = record.get("regulator")
        record_id = str(record.get("source_record_id", ""))
        if host is None or entity is None:
            counts["iosco_missing_single_host_or_entity"] += 1
            continue
        if record.get("quality_flags") not in ([], None):
            counts["iosco_quality_flag"] += 1
            continue
        parsed_notice = urlparse(notice_url)
        if parsed_notice.scheme != "https" or not parsed_notice.netloc:
            counts["iosco_invalid_notice_url"] += 1
            continue
        if parsed_notice.hostname in {host, f"www.{host}"}:
            counts["iosco_notice_is_candidate_host"] += 1
            continue
        if not isinstance(regulator, dict) or not regulator.get("name") or not regulator.get("jurisdiction"):
            counts["iosco_missing_regulator"] += 1
            continue
        host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
        if host_hash in opened_host_hashes or record_id in opened_source_records:
            counts["iosco_opened_overlap"] += 1
            continue
        iosco_hosts.add(host)
        iosco_rows.append(
            base_row(
                record,
                source_id="iosco_i_scan",
                source_record_id=record_id,
                reference_url=notice_url,
                reference_sha256=iosco_index_sha,
                observed_at=args.observed_at,
                entity=entity,
                host=host,
            )
        )

    sec_host_counts = Counter(
        host
        for record in sec_records
        for host in [clean_host(record)]
        if host is not None
    )
    sec_rows: list[dict] = []
    for record in sec_records:
        host = clean_host(record)
        entity = entity_name(record)
        record_id = str(record.get("source_record_id", ""))
        registration = record.get("registration")
        if host is None or entity is None:
            counts["sec_missing_single_host_or_entity"] += 1
            continue
        if record.get("quality_flags") not in ([], None):
            counts["sec_quality_flag"] += 1
            continue
        if not isinstance(registration, dict) or registration.get("firm_type") != "Registered" or registration.get("status") != "APPROVED":
            counts["sec_not_registered_approved"] += 1
            continue
        if sec_host_counts[host] != 1 or host in iosco_hosts:
            counts["sec_shared_or_iosco_host"] += 1
            continue
        if not record.get("sec_number"):
            counts["sec_missing_number"] += 1
            continue
        host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()
        if host_hash in opened_host_hashes or record_id in opened_source_records:
            counts["sec_opened_overlap"] += 1
            continue
        sec_rows.append(
            base_row(
                record,
                source_id="sec_iapd",
                source_record_id=record_id,
                reference_url=f"https://adviserinfo.sec.gov/firm/summary/{record_id}",
                reference_sha256=sec_index_sha,
                observed_at=args.observed_at,
                entity=entity,
                host=host,
            )
        )
    if len({row["normalized_host"] for row in iosco_rows}) < 10 or len(sec_rows) < 10:
        raise ValueError("Insufficient normalized existing-channel pools")
    write_jsonl(args.iosco_output, iosco_rows)
    write_jsonl(args.sec_output, sec_rows)
    report = {
        "analysis_id": "ISI_TARGET_TEXT_CORPUS_V1_EXISTING_REFERENCE_NORMALIZATION_V1",
        "status": "FROZEN_REFERENCE_POOLS_UNLABELED_NOT_CAPTURED",
        "inputs": {
            "iosco": {"path": str(args.iosco_index), "sha256": iosco_index_sha},
            "sec_iapd": {"path": str(args.sec_iapd_index), "sha256": sec_index_sha},
            "exclusion_index": {
                "path": str(args.exclusion_index),
                "sha256": sha256_file(args.exclusion_index),
            },
        },
        "outputs": {
            "confirmed_regulator": {
                "path": str(args.iosco_output),
                "sha256": sha256_file(args.iosco_output),
                "record_count": len(iosco_rows),
                "unique_host_count": len({row["normalized_host"] for row in iosco_rows}),
            },
            "legitimate_iapd": {
                "path": str(args.sec_output),
                "sha256": sha256_file(args.sec_output),
                "record_count": len(sec_rows),
                "unique_host_count": len({row["normalized_host"] for row in sec_rows}),
            },
        },
        "exclusion_counts": dict(sorted(counts.items())),
        "safety_contract": {
            "network_operations": 0,
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
