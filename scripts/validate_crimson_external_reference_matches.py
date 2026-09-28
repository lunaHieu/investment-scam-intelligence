"""Validate frozen Crimson external-reference matches and review queue."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.matching.external_domain_references import queue_reason
from src.isi.normalization.external_references import sha256_file


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    errors: list[str] = []

    inputs = report.get("inputs", {})
    for name in ("crimson", "iosco", "sec"):
        path = Path(str(inputs.get(f"{name}_path", "")))
        expected = inputs.get(f"{name}_sha256")
        if not path.is_file():
            errors.append(f"missing {name} input: {path}")
        elif sha256_file(path) != expected:
            errors.append(f"{name} input SHA-256 mismatch")

    outputs = report.get("outputs", {})
    matches_info = outputs.get("reference_matches", {})
    queue_info = outputs.get("review_queue", {})
    matches_path = Path(str(matches_info.get("path", "")))
    queue_path = Path(str(queue_info.get("path", "")))
    matches = load_jsonl(matches_path) if matches_path.is_file() else []
    queue = load_jsonl(queue_path) if queue_path.is_file() else []
    for name, path, info in (
        ("reference_matches", matches_path, matches_info),
        ("review_queue", queue_path, queue_info),
    ):
        if not path.is_file():
            errors.append(f"missing {name}: {path}")
            continue
        if sha256_file(path) != info.get("sha256"):
            errors.append(f"{name} SHA-256 mismatch")
        records = matches if name == "reference_matches" else queue
        if len(records) != info.get("record_count"):
            errors.append(f"{name} record count mismatch")

    match_ids: set[str] = set()
    matches_by_host: dict[str, list[dict[str, object]]] = defaultdict(list)
    relation_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    ambiguous_count = 0
    for line_number, match in enumerate(matches, start=1):
        match_id = str(match.get("match_id") or "")
        if not match_id or match_id in match_ids:
            errors.append(f"missing or duplicate match_id at match line {line_number}")
            break
        match_ids.add(match_id)
        if match.get("label_created") is not False or match.get("identity_resolved") is not False:
            errors.append(f"unsafe decision field at match line {line_number}")
            break
        if match.get("review_status") != "UNREVIEWED":
            errors.append(f"unexpected review status at match line {line_number}")
            break
        crimson_host = str(match.get("crimson_match_host") or "")
        reference_host = str(match.get("matched_reference_host") or "")
        relation = str(match.get("host_relation") or "")
        if relation == "EXACT_HOST":
            valid_relation = crimson_host == reference_host
        elif relation == "CRIMSON_SUBDOMAIN_OF_REFERENCE_HOST":
            valid_relation = crimson_host.endswith("." + reference_host)
        elif relation == "REFERENCE_SUBDOMAIN_OF_CRIMSON_HOST":
            valid_relation = reference_host.endswith("." + crimson_host)
        else:
            valid_relation = False
        if not valid_relation:
            errors.append(f"invalid host relation at match line {line_number}")
            break
        matches_by_host[crimson_host].append(match)
        relation_counts[relation] += 1
        source_counts[str(match.get("match_source_id"))] += 1
        ambiguous_count += int(int(match.get("reference_host_record_count", 0)) > 1)

    queue_hosts: set[str] = set()
    queue_artifact_ids: set[str] = set()
    reason_counts: Counter[str] = Counter()
    for expected_rank, record in enumerate(queue, start=1):
        host = str(record.get("crimson_match_host") or "")
        if not host or host in queue_hosts:
            errors.append(f"missing or duplicate queue host at rank {expected_rank}")
            break
        queue_hosts.add(host)
        if record.get("queue_rank") != expected_rank:
            errors.append(f"queue rank mismatch at rank {expected_rank}")
            break
        if record.get("label_created") is not False or record.get("identity_resolved") is not False:
            errors.append(f"unsafe decision field at queue rank {expected_rank}")
            break
        host_matches = matches_by_host.get(host, [])
        unique_reference_matches = {
            (str(item.get("match_source_id")), str(item.get("reference_record_id"))): item
            for item in host_matches
        }
        expected_reason = queue_reason(list(unique_reference_matches.values())) if host_matches else None
        if record.get("queue_reason") != expected_reason:
            errors.append(f"queue reason mismatch at rank {expected_rank}")
            break
        expected_ids = {
            source_id: sorted({
                reference_id
                for (match_source, reference_id) in unique_reference_matches
                if match_source == source_id
            })
            for source_id in ("iosco_i_scan", "sec_iapd")
        }
        if record.get("reference_record_ids") != expected_ids:
            errors.append(f"queue reference IDs mismatch at rank {expected_rank}")
            break
        artifact_ids = record.get("crimson_artifact_ids", [])
        if not isinstance(artifact_ids, list) or not artifact_ids:
            errors.append(f"queue artifact IDs missing at rank {expected_rank}")
            break
        if queue_artifact_ids.intersection(map(str, artifact_ids)):
            errors.append(f"artifact appears in multiple queue rows at rank {expected_rank}")
            break
        queue_artifact_ids.update(map(str, artifact_ids))
        reason_counts[str(record.get("queue_reason"))] += 1

    coverage = report.get("coverage", {})
    expected_checks = {
        "reference_match_pair_count": len(matches),
        "unique_crimson_match_hosts_with_reference_match": len(queue),
        "crimson_records_with_reference_match": len(queue_artifact_ids),
        "ambiguous_match_pair_count": ambiguous_count,
        "pair_counts_by_source": dict(sorted(source_counts.items())),
        "pair_counts_by_host_relation": dict(sorted(relation_counts.items())),
        "queue_counts_by_reason": dict(sorted(reason_counts.items())),
    }
    for key, observed in expected_checks.items():
        if coverage.get(key) != observed:
            errors.append(f"coverage mismatch: {key}")

    safety = report.get("safety_contract", {})
    if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
        errors.append("safety counts must remain zero")
    if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
        errors.append("training/domain-access gates must remain closed")
    if safety.get("automatic_entity_resolution_allowed") is not False:
        errors.append("automatic identity resolution must remain blocked")

    result = {
        "status": "VALID" if not errors else "INVALID",
        "match_record_count": len(matches),
        "review_queue_count": len(queue),
        "queue_counts_by_reason": dict(sorted(reason_counts.items())),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
