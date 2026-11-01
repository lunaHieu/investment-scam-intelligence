"""Freeze the owner's Crimson primary confirmations and safe next-stage packets.

This offline workflow consumes hash-pinned review artifacts and source notes.
It never opens a Crimson candidate host, creates a scam/legitimacy label, or
marks any row eligible for training. Blind second review remains assigned to a
different human reviewer and is not performed by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
READY = "READY_FOR_TRUTHFUL_HUMAN_PRIMARY_REVIEW"
FOLLOWUP = "OFFICIAL_REFERENCE_FOLLOWUP_REQUIRED"
IDENTITY_VALUES = {"SAME_ENTITY", "IMPERSONATION_SUSPECTED", "UNRELATED", "UNCLEAR"}
EVIDENCE_VALUES = {
    "WARNING_RELEVANT",
    "REGISTRATION_RELEVANT",
    "REFERENCE_NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE",
}
BLIND_FIELDS = [
    "identity_suggestion",
    "evidence_suggestion",
    "first_reviewer",
    "first_review_decision",
    "first_review_notes",
    "owner_primary_decision",
    "owner_primary_notes",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object at {path}:{number}")
        rows.append(value)
    return rows


def verify_inputs(input_specs: dict[str, dict[str, str]]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for role, spec in input_specs.items():
        path = Path(spec["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Missing pinned input {role}: {path}")
        actual = sha256_file(path)
        if actual.lower() != spec["sha256"].lower():
            raise ValueError(f"Pinned input hash mismatch for {role}: {actual}")
        paths[role] = path
    return paths


def build_artifacts(
    readiness: dict[str, Any],
    first_pass_rows: list[dict[str, Any]],
    plan_rows: list[dict[str, Any]],
    existing_decisions: list[dict[str, Any]],
    followup_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    if readiness.get("status") != "PASS_39_PRIMARY_TASKS_INTEGRITY_VERIFIED_24_READY_15_FOLLOWUP_REQUIRED":
        raise ValueError("Frozen readiness status changed")
    counts = readiness.get("counts", {})
    if counts.get("pending_primary_tasks") != 39:
        raise ValueError("Expected the frozen 39-task primary-review snapshot")
    if counts.get("ready_for_truthful_human_primary_review") != 24:
        raise ValueError("Expected exactly 24 readiness-passed tasks")
    if counts.get("official_reference_followup_required") != 15:
        raise ValueError("Expected exactly 15 official-reference follow-ups")
    if counts.get("second_review_required_after_primary") != 20:
        raise ValueError("Expected 20 pending tasks that require second review")

    first_by_id = {row.get("pilot_id"): row for row in first_pass_rows}
    plan_by_id = {row.get("pilot_id"): row for row in plan_rows}
    if len(first_by_id) != 40 or len(plan_by_id) != 40:
        raise ValueError("The first-pass and review-plan inputs must each have 40 unique pilots")
    if len(existing_decisions) != 1 or existing_decisions[0].get("pilot_id") != "PILOT_CRIMSON_REF_018":
        raise ValueError("The immutable prior-decision population changed")

    ready_rows = [row for row in readiness.get("records", []) if row.get("readiness") == READY]
    unresolved_followups = [row for row in readiness.get("records", []) if row.get("readiness") == FOLLOWUP]
    if len(ready_rows) != 24 or len(unresolved_followups) != 15 or len(followup_rows) != 15:
        raise ValueError("The frozen readiness partition or follow-up packet changed")
    if {row.get("pilot_id") for row in unresolved_followups} != {row.get("pilot_id") for row in followup_rows}:
        raise ValueError("Readiness and follow-up packet identities do not match")

    owner = config["owner_confirmation"]
    reviewer = str(owner["reviewer"]).strip()
    confirmation_text = str(owner["confirmation_text"]).strip()
    confirmation_source = str(owner["confirmation_source"]).strip()
    reviewed_date = str(owner["reviewed_date"])
    if not reviewer or not confirmation_text or not confirmation_source:
        raise ValueError("Owner identity, exact confirmation and provenance are required")

    owner_decisions: list[dict[str, Any]] = []
    blind_handoff: list[dict[str, Any]] = []
    single_review_reconciliation: list[dict[str, Any]] = []
    for ready in sorted(ready_rows, key=lambda row: row["pilot_id"]):
        pilot_id = ready["pilot_id"]
        source = first_by_id.get(pilot_id)
        plan = plan_by_id.get(pilot_id)
        if source is None or plan is None:
            raise ValueError(f"Missing pinned source for {pilot_id}")
        if source.get("review_stage") != "AI_ASSISTED_FIRST_PASS" or source.get("review_status") != "IN_PROGRESS":
            raise ValueError(f"Unexpected first-pass state for {pilot_id}")
        if source.get("human_confirmation_required") is not True or source.get("official_reference_checked") != "YES":
            raise ValueError(f"The source row is not eligible for owner confirmation: {pilot_id}")
        identity = source.get("identity_relationship")
        evidence = source.get("evidence_assessment")
        if identity not in IDENTITY_VALUES or evidence not in EVIDENCE_VALUES:
            raise ValueError(f"Unsupported review values for {pilot_id}")
        if ready.get("second_review_required") is not plan.get("second_review_required"):
            raise ValueError(f"Second-review requirement mismatch for {pilot_id}")

        second_required = bool(ready["second_review_required"])
        decision_id = f"{pilot_id}_OWNER_CONFIRMED_PRIMARY_V1"
        decision = {
            "decision_id": decision_id,
            "pilot_id": pilot_id,
            "pilot_rank": int(plan["pilot_rank"]),
            "crimson_host": source["crimson_host"],
            "decision_stage": "HUMAN_FIRST_REVIEW",
            "review_status": "COMPLETED",
            "review_method": "OWNER_DECLARED_PRIOR_REVIEW_AND_APPROVAL_OF_FROZEN_RECOMMENDATION",
            "official_reference_checked": "YES_AS_RECORDED_IN_PINNED_FIRST_PASS",
            "identity_relationship": identity,
            "evidence_assessment": evidence,
            "reviewer": reviewer,
            "reviewed_date": reviewed_date,
            "review_notes": (
                "The project owner explicitly stated that they had reviewed Crimson and agreed with its decision. "
                "This record applies that confirmation only to the readiness-passed frozen recommendation for this row. "
                "The identity/evidence assessment is copied unchanged from the pinned first-pass record; no new source "
                "fact is asserted by this recorder. It is not a scam/legitimacy label."
            ),
            "second_review_required": second_required,
            "second_review_status": "REQUESTED" if second_required else "NOT_REQUIRED_BY_PLAN",
            "second_reviewer": "",
            "adjudication_status": "SECOND_REVIEW_REQUIRED" if second_required else "READY_FOR_SINGLE_REVIEW_RECONCILIATION",
            "confirmation_text": confirmation_text,
            "confirmation_source": confirmation_source,
            "source_first_pass_sha256": sha256_bytes(
                json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ),
            "source_reference_record_ids": source.get("reference_record_ids", [source.get("reference_record_id")]),
            "live_reference_status": source.get("live_reference_status", "NOT_TRACKED_BY_SOURCE_RECORD"),
            "human_confirmation_recorded": True,
            "label_created": False,
            "model_label_disposition": "UNCERTAIN",
            "training_eligible": "NO",
        }
        owner_decisions.append(decision)

        if second_required:
            blind_handoff.append({
                "task_id": f"CRIMSON_SECOND_OWNERCONFIRMED_{pilot_id}",
                "task_type": "BLIND_HUMAN_SECOND_REVIEW",
                "dependency_status": "READY_FOR_TRULY_INDEPENDENT_HUMAN_REVIEWER",
                "pilot_id": pilot_id,
                "pilot_rank": int(plan["pilot_rank"]),
                "crimson_host": plan["crimson_host"],
                "do_not_open_crimson_host": True,
                "reference_source": plan["reference_source"],
                "reference_record_ids": plan["reference_record_ids"],
                "official_reference_urls": plan["official_reference_urls"],
                "allowed_identity_relationships": sorted(IDENTITY_VALUES),
                "allowed_evidence_assessments": sorted(EVIDENCE_VALUES),
                "blind_fields_omitted": BLIND_FIELDS,
                "review_status": "NOT_STARTED",
                "second_reviewer": "",
                "model_label_disposition": "UNCERTAIN",
                "training_eligible": "NO",
                "label_created": False,
            })
        else:
            single_review_reconciliation.append({
                "reconciliation_id": f"{pilot_id}_SINGLE_REVIEW_RECONCILIATION_V1",
                "pilot_id": pilot_id,
                "reviewer_count": 1,
                "second_review_required": False,
                "primary_decision_id": decision_id,
                "identity_relationship": identity,
                "evidence_assessment": evidence,
                "reconciliation_status": "PRIMARY_RECOMMENDATION_CONFIRMED_NO_SECOND_REVIEW_REQUIRED",
                "disagreement_status": "NOT_APPLICABLE_SINGLE_REVIEW_PLAN",
                "model_label_disposition": "UNCERTAIN",
                "label_created": False,
                "training_eligible": "NO",
                "rationale": (
                    "The owner confirmed the frozen primary identity/evidence recommendation. SEC/IAPD registration "
                    "or an official warning reference is not, by itself, ground truth for scam versus legitimate."
                ),
            })

    prior = existing_decisions[0]
    if prior.get("review_status") != "COMPLETED" or prior.get("decision_stage") != "HUMAN_FIRST_REVIEW":
        raise ValueError("The prior P18 primary decision is invalid")
    p18 = plan_by_id.get(prior["pilot_id"])
    if p18 is None or p18.get("second_review_required") is not True:
        raise ValueError("P18 must remain in the blind second-review population")
    blind_handoff.insert(0, {
        "task_id": f"CRIMSON_SECOND_PRIOR_{prior['pilot_id']}",
        "task_type": "BLIND_HUMAN_SECOND_REVIEW",
        "dependency_status": "READY_FOR_TRULY_INDEPENDENT_HUMAN_REVIEWER",
        "pilot_id": prior["pilot_id"],
        "pilot_rank": int(p18["pilot_rank"]),
        "crimson_host": p18["crimson_host"],
        "do_not_open_crimson_host": True,
        "reference_source": p18["reference_source"],
        "reference_record_ids": p18["reference_record_ids"],
        "official_reference_urls": p18["official_reference_urls"],
        "allowed_identity_relationships": sorted(IDENTITY_VALUES),
        "allowed_evidence_assessments": sorted(EVIDENCE_VALUES),
        "blind_fields_omitted": BLIND_FIELDS,
        "review_status": "NOT_STARTED",
        "second_reviewer": "",
        "model_label_disposition": "UNCERTAIN",
        "training_eligible": "NO",
        "label_created": False,
    })

    if len(owner_decisions) != 24 or len(blind_handoff) != 9 or len(single_review_reconciliation) != 16:
        raise ValueError("Expected 24 primary confirmations, 9 blind tasks and 16 single-review reconciliations")
    if len({row["pilot_id"] for row in owner_decisions}) != 24:
        raise ValueError("Owner-confirmed pilot identities must be unique")

    source_evidence = config.get("official_source_observations", [])
    followup_by_id = {row["pilot_id"]: row for row in followup_rows}
    if len(source_evidence) != 6:
        raise ValueError("Expected exactly six newly recorded official-source observations")
    source_rows: list[dict[str, Any]] = []
    for observation in source_evidence:
        pilot_id = observation["pilot_id"]
        followup = followup_by_id.get(pilot_id)
        if followup is None or observation["source_url"] not in followup["official_reference_urls"]:
            raise ValueError(f"Source observation is not in the frozen follow-up packet: {pilot_id}")
        source_rows.append({
            "task_id": followup["task_id"],
            "pilot_id": pilot_id,
            "crimson_host": followup["crimson_host"],
            "reference_record_ids": followup["reference_record_ids"],
            "official_source_url": observation["source_url"],
            "source_title": observation["source_title"],
            "retrieved_on": observation["retrieved_on"],
            "observed_facts": observation["observed_facts"],
            "interpretation_limit": observation["interpretation_limit"],
            "raw_page_retained": False,
            "raw_page_sha256": None,
            "human_primary_review_status": "PENDING",
            "model_label_disposition": "UNCERTAIN",
            "label_created": False,
            "training_eligible": "NO",
        })

    access_status: list[dict[str, Any]] = []
    status_by_url = {item["url"]: item for item in config["official_reference_access_status"]}
    for followup in followup_rows:
        url_statuses = []
        for url in followup["official_reference_urls"]:
            status = status_by_url.get(url)
            if status is None:
                raise ValueError(f"No access-status record for official reference URL: {url}")
            url_statuses.append({
                "url": url,
                "status": status["status"],
                "checked_on": status["checked_on"],
                "note": status["note"],
                "same_url_retry_allowed": status["same_url_retry_allowed"],
            })
        access_status.append({
            "task_id": followup["task_id"],
            "pilot_id": followup["pilot_id"],
            "crimson_host": followup["crimson_host"],
            "official_references": url_statuses,
            "overall_status": (
                "PARTIAL_OFFICIAL_EVIDENCE_CAPTURED_PRIMARY_REVIEW_PENDING"
                if any(item["status"] == "PAGE_CONTENT_REVIEWED" for item in url_statuses)
                else "OFFICIAL_REFERENCE_ACCESS_OR_MATCH_UNRESOLVED"
            ),
            "decision": "DO_NOT_ADMIT_OR_LABEL_UNTIL_HUMAN_REVIEW_IS_RECORDED",
            "label_created": False,
            "training_eligible": "NO",
        })
    return {
        "owner_confirmed_primary_decisions": owner_decisions,
        "blind_second_review_handoff": blind_handoff,
        "single_review_reconciliation": single_review_reconciliation,
        "official_source_evidence": source_rows,
        "official_source_access_status": access_status,
    }


def write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def materialize(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    input_paths = verify_inputs(config["inputs"])
    readiness = load_json(input_paths["readiness_report"])
    first_pass = load_jsonl(input_paths["sec_first_pass"]) + load_jsonl(input_paths["iosco_first_pass"])
    plan = load_jsonl(input_paths["review_plan"])
    old_decisions = load_jsonl(input_paths["existing_decisions"])
    followups = load_jsonl(input_paths["official_reference_followup"])
    artifacts = build_artifacts(readiness, first_pass, plan, old_decisions, followups, config)

    output_paths = {role: Path(raw) for role, raw in config["outputs"].items()}
    registry_path = ROOT / "registry/analyses/crimson_owner_review_progress_v1.json"
    if set(output_paths) != set(artifacts):
        raise ValueError("Configured output roles do not match the workflow contract")
    if any(path.exists() for path in output_paths.values()) or registry_path.exists():
        raise FileExistsError("Refusing to overwrite a Crimson review-progress output")

    for role, rows in artifacts.items():
        write_jsonl_exclusive(output_paths[role], rows)

    registry = {
        "analysis_id": "ISI_CRIMSON_OWNER_REVIEW_PROGRESS_V1",
        "created_at": config["owner_confirmation"]["reviewed_date"],
        "status": "PASS_24_OWNER_PRIMARY_CONFIRMED_16_SINGLE_RECONCILED_9_BLIND_READY_15_FOLLOWUP_OPEN",
        "inputs": [
            {"role": role, "path": str(path), "sha256": sha256_file(path)}
            for role, path in input_paths.items()
        ] + [{"role": "workflow_config", "path": str(config_path), "sha256": sha256_file(config_path)}],
        "implementation": [{
            "role": "owner_review_progress_materializer",
            "path": "scripts/record_crimson_owner_review_progress_v1.py",
            "sha256": sha256_file(ROOT / "scripts/record_crimson_owner_review_progress_v1.py"),
        }],
        "outputs": [
            {"role": role, "path": str(path), "sha256": sha256_file(path), "record_count": len(artifacts[role])}
            for role, path in output_paths.items()
        ],
        "counts": {
            "prior_primary_decisions_preserved": len(old_decisions),
            "owner_confirmed_primary_decisions": len(artifacts["owner_confirmed_primary_decisions"]),
            "single_review_reconciliations": len(artifacts["single_review_reconciliation"]),
            "blind_second_review_ready": len(artifacts["blind_second_review_handoff"]),
            "blind_second_review_waiting": 12,
            "primary_review_pending": 15,
            "official_reference_evidence_rows_recorded": len(artifacts["official_source_evidence"]),
            "official_followup_tasks_still_open": len(artifacts["official_source_access_status"]),
            "unresolved_official_source_urls": sum(
                item["status"] != "PAGE_CONTENT_REVIEWED"
                for row in artifacts["official_source_access_status"]
                for item in row["official_references"]
            ),
            "labels_created": 0,
            "training_eligible_records": 0,
        },
        "owner_confirmation": config["owner_confirmation"],
        "decision": {
            "confirmation_scope": "Only 24 pre-existing readiness-passed frozen primary recommendations",
            "15_followup_rows_owner_confirmed": False,
            "16_single_review_rows_reconciled_at_identity_evidence_level": True,
            "9_blind_reviews_completed": False,
            "12_waiting_blind_reviews_opened": False,
            "label_materialization_allowed": False,
            "training_allowed": False,
            "source_evidence_admission_allowed": False,
        },
        "safety_contract": {
            "candidate_domain_access_operations": 0,
            "official_reference_source_pages_reviewed": 6,
            "raw_official_page_artifacts_retained": 0,
            "labels_created": 0,
            "training_allowed": False,
        },
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(registry, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs/crimson_owner_review_progress_v1.json",
    )
    args = parser.parse_args()
    result = materialize(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
