"""Build the exact 53-row eligible ready-channel archive capture plan offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PASS_BULK_QA = "PASS_COMPLETE_EXACT_68_CDX_METADATA_CAPTURE_PLAN_MAY_BE_PREPARED"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(item: dict[str, Any]) -> Path:
    path = Path(str(item["path"]))
    return path if item.get("absolute") else ROOT / path


def safe(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    if not result or result in {".", ".."}:
        raise ValueError(f"unsafe path component: {value!r}")
    return result


def verify_input(item: dict[str, Any]) -> Path:
    path = resolve(item)
    if not path.is_file() or sha256_file(path) != item["sha256"]:
        raise ValueError(f"input hash mismatch: {path}")
    return path


def build(release_path: Path) -> dict[str, Any]:
    release = load_json(release_path)
    if release.get("release_id") != "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_PLAN_RELEASE_V1":
        raise ValueError("unexpected release id")
    if release.get("status") != "FROZEN_EXACT_53_ELIGIBLE_ONLY_CAPTURE_PLAN_RELEASE":
        raise ValueError("release is not frozen")
    paths = {key: verify_input(value) for key, value in release["inputs"].items()}
    canary = load_json(paths["canary_report"])
    canary_qa = load_json(paths["canary_result_qa"])
    canary_release = load_json(paths["canary_release"])
    bulk = load_json(paths["bulk_report"])
    bulk_qa = load_json(paths["bulk_result_qa"])
    if canary.get("status") != "COMPLETE_VALID_CDX_CANARY_WITH_ELIGIBLE_METADATA":
        raise ValueError("canary result is not complete")
    if canary_qa.get("status") != "PASS_CDX_CANARY_VALID_BULK_RELEASE_MAY_BE_PREPARED":
        raise ValueError("canary QA did not pass")
    if bulk.get("status") != "COMPLETE_EXACT_68_CDX_METADATA":
        raise ValueError("bulk result is not complete")
    if bulk_qa.get("status") != PASS_BULK_QA or not bulk_qa["decision"]["capture_plan_may_be_prepared"]:
        raise ValueError("bulk QA did not open capture-plan preparation")
    canary_source = {
        **canary_release["target_record"],
        "outcome": "COMPLETE_VALID_CDX_METADATA",
        "enumeration": canary["enumeration"],
    }
    source_rows = [canary_source, *bulk["results"]]
    expected_ids = [f"TTCV1_B3_AVAIL_{index:03d}" for index in range(2, 71)]
    actual_ids = [str(row["availability_plan_id"]) for row in source_rows]
    if actual_ids != expected_ids:
        raise ValueError("resolved population is not exact ordered rows 002-070")
    capture_root = Path(release["capture_contract"]["capture_root"]).resolve()
    raw_root = Path(release["capture_contract"]["raw_root"]).resolve()
    if raw_root not in capture_root.parents:
        raise ValueError("capture root escapes raw root")
    rows: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for source in source_rows:
        selected = source.get("enumeration", {}).get("selected_candidate")
        if source.get("outcome") != "COMPLETE_VALID_CDX_METADATA":
            raise ValueError(f"incomplete metadata result: {source.get('availability_plan_id')}")
        if not selected:
            unavailable.append(str(source["availability_plan_id"]))
            continue
        plan_id = str(source["availability_plan_id"])
        candidate_id = str(source["candidate_id"])
        timestamp = str(selected["timestamp"])
        original = str(selected["original"])
        requested = str(selected["requested_archive_url"])
        if requested != f"https://web.archive.org/web/{timestamp}id_/{original}":
            raise ValueError(f"raw replay mismatch: {plan_id}")
        target = (capture_root / safe(str(source["cohort"])) / safe(str(source["channel_id"])) / f"{safe(plan_id)}__{safe(candidate_id)}.html").resolve()
        if capture_root not in target.parents or target.exists():
            raise ValueError(f"invalid or existing capture target: {target}")
        rows.append({
            "capture_plan_id": plan_id.replace("AVAIL", "CAPTURE"),
            "availability_plan_id": plan_id,
            "candidate_id": candidate_id,
            "cohort": source["cohort"],
            "channel_id": source["channel_id"],
            "candidate_host": source["candidate_host"],
            "snapshot_timestamp": timestamp,
            "snapshot_original_url": original,
            "snapshot_digest": selected["digest"],
            "requested_archive_url": requested,
            "capture_path": str(target),
        })
    counts = Counter(row["cohort"] for row in rows)
    if len(rows) != 53 or counts != {"DEVELOPMENT": 37, "EXTERNAL_HOLDOUT": 16}:
        raise ValueError(f"population changed: rows={len(rows)}, cohorts={dict(counts)}")
    if unavailable != release["population_contract"]["no_eligible_snapshot_rows"]:
        raise ValueError("empty-metadata membership changed")
    return {
        "plan_id": "ISI_TARGET_TEXT_CORPUS_V1_READY_CHANNEL_CAPTURE_PLAN_V1",
        "created_at": release["created_at"],
        "status": "FROZEN_EXACT_53_ELIGIBLE_ONLY_RAW_WAYBACK_CAPTURE_PLAN",
        "release": {"path": str(release_path.resolve()), "sha256": sha256_file(release_path)},
        "inputs": release["inputs"],
        "resolved_metadata_rows": 69,
        "planned_capture_count": 53,
        "planned_by_cohort": dict(counts),
        "no_eligible_snapshot_count": 16,
        "no_eligible_snapshot_rows": unavailable,
        "results": rows,
        "decision": {"capture_execution_authorized": False, "separate_capture_release_required": True, "candidate_live_domain_access_allowed": False, "labeling_allowed": False, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "candidate_domain_access_operations": 0, "archived_page_downloads": 0, "captures": 0, "labels_created": 0, "model_operations": 0, "training_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    plan = build(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": plan["status"], "planned_capture_count": 53, "output": str(args.output), "sha256": sha256_file(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
