"""Record the owner's frozen policy decision against a pending V2 packet."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


def build(packet_path: Path, authorization_path: Path) -> dict[str, Any]:
    packet = load_object(packet_path)
    authorization = load_object(authorization_path)
    if packet.get("acceptance_id") != "ISI_SEC_EDGAR_IAPD_OWNER_ACCEPTANCE_V2" or packet.get("status") != "PENDING_OWNER_DECISIONS":
        raise ValueError("Unexpected pending owner-acceptance packet")
    if authorization.get("authorization_id") != "ISI_SEC_EDGAR_IAPD_OWNER_AUTHORIZATION_V2" or authorization.get("status") != "FROZEN_OWNER_AUTHORIZATION":
        raise ValueError("Unexpected owner authorization")
    if authorization.get("reconciliation_sha256") != packet.get("reconciliation_sha256") or authorization.get("reconciliation_qa_sha256") != packet.get("reconciliation_qa_sha256"):
        raise ValueError("Owner authorization is not bound to the pending packet inputs")
    attestation = authorization.get("owner_attestation", {})
    if attestation.get("reviewed_reconciliation_snapshot") is not True or attestation.get("explicit_acceptance") is not True:
        raise ValueError("Owner attestation is incomplete")
    if attestation.get("independent_evidence_rereview_claimed") is not False:
        raise ValueError("Authorization must not claim an independent evidence rereview")
    policy = authorization.get("decision_policy", {})
    if policy.get("accept_all_reconciled_legitimate") is not True or policy.get("retain_all_uncertain_without_label") is not True:
        raise ValueError("Owner decision policy is incomplete")
    if policy.get("external_holdout_training_allowed") is not False or policy.get("training_allowed_now") is not False:
        raise ValueError("Owner authorization prematurely opens training")
    if not isinstance(authorization.get("authorization_source"), str) or len(authorization["authorization_source"].strip()) < 40:
        raise ValueError("Owner authorization source is not substantive")

    result = copy.deepcopy(packet)
    counts: Counter[str] = Counter()
    for row in result.get("records", []):
        recommendation = row.get("reconciled_recommendation")
        counts[str(recommendation)] += 1
        if recommendation == "LEGITIMATE":
            row["accepted"] = True
            row["rationale"] = (
                "Owner accepts the frozen reconciled LEGITIMATE recommendation after reviewing the reported reconciliation snapshot; "
                "label materialization remains separate from dataset release and training eligibility."
            )
        elif recommendation == "UNCERTAIN":
            row["accepted"] = False
            row["rationale"] = (
                "Owner retains the frozen UNCERTAIN recommendation because evidence was insufficient or reviewers disagreed; "
                "no binary label or training eligibility is authorized."
            )
        else:
            raise ValueError(f"Unexpected packet recommendation: {row.get('record_id')}")
    expected = authorization.get("scope", {}).get("expected_recommendations")
    if dict(counts) != expected:
        raise ValueError(f"Owner authorization population mismatch: {dict(counts)}")
    if len(result.get("records", [])) != authorization.get("scope", {}).get("expected_records"):
        raise ValueError("Owner authorization record count mismatch")

    result["status"] = "OWNER_DECISIONS_COMPLETE"
    result["accepted_at"] = authorization.get("accepted_at")
    result["adopter_role"] = authorization.get("adopter_role")
    result["authorization_source"] = authorization.get("authorization_source")
    result["authorization_sha256"] = sha256_file(authorization_path)
    result["owner_attestation"] = copy.deepcopy(attestation)
    result["decision"] = {
        "owner_review_complete": True,
        "label_materialization_allowed": True,
        "training_allowed": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite completed owner acceptance")
    result = build(args.packet, args.authorization)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"acceptance_id": result["acceptance_id"], "status": result["status"], "record_count": len(result["records"]), "output": str(args.output), "sha256": sha256_file(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
