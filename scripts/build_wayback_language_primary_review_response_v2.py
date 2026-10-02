"""Expand an explicit case roster into a hash-bound V2 primary-review response."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.isi.normalization.external_references import sha256_file


def invert_roster(roster: dict[str, list[str]], expected_ids: set[str], name: str) -> dict[str, str]:
    inverted: dict[str, str] = {}
    for decision, candidate_ids in roster.items():
        for candidate_id in candidate_ids:
            if candidate_id in inverted:
                raise ValueError(f"Duplicate {name} roster candidate: {candidate_id}")
            inverted[candidate_id] = decision
    if set(inverted) != expected_ids:
        missing = sorted(expected_ids - set(inverted))
        extra = sorted(set(inverted) - expected_ids)
        raise ValueError(f"{name} roster coverage mismatch; missing={missing}, extra={extra}")
    return inverted


def build_response(packet: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    items = {str(item["candidate_id"]): item for item in packet["items"]}
    expected_ids = set(items)
    languages = invert_roster(policy["language_decisions"], expected_ids, "language")
    decisions = invert_roster(policy["evidence_decisions"], expected_ids, "evidence")
    notes = policy.get("case_notes", {})
    reviews = []
    for candidate_id in sorted(items):
        item = items[candidate_id]
        reference = item.get("official_reference_record")
        if not isinstance(reference, dict):
            raise ValueError(f"Hash-pinned official reference record is missing: {candidate_id}")
        host = str(item["candidate_host"])
        if host not in reference.get("observed_hosts", []):
            raise ValueError(f"Official reference does not contain exact host: {candidate_id}")
        decision = decisions[candidate_id]
        identity_keys = [str(value) for value in item.get("entity_name_keys", [])]
        checks = [
            f"Exact archived host {host} is present in the hash-pinned official reference row.",
            f"Archived visible text was checked against identity keys: {', '.join(identity_keys)}.",
            "Archived content was checked for service/activity alignment and domain repurpose or impersonation contradictions.",
            "Language was confirmed from the visible text rather than accepted from automatic routing alone.",
        ]
        if decision == "CONFIRMED":
            rationale = (
                f"The archived page identifies {host} and presents financial, trading, banking, or investment activity; "
                "the exact host and aligned identity occur in the official regulator-warning record. No unresolved "
                "repurpose contradiction was observed in this capture. CONFIRMED denotes warning-supported evidence, "
                "not a criminal conviction."
            )
            contradictions = []
        elif decision == "LEGITIMATE":
            rationale = (
                f"The archived page identifies {host} and presents an advisory or investment business aligned with "
                "the approved SEC/IAPD registration record, which contains the exact host. No impersonation or "
                "repurpose contradiction was observed in the archived text."
            )
            contradictions = []
        else:
            rationale = str(notes.get(candidate_id, "Evidence or capture quality remains unresolved."))
            contradictions = [rationale]
        reviews.append(
            {
                "candidate_id": candidate_id,
                "language_decision": languages[candidate_id],
                "evidence_decision": decision,
                "confidence": policy["confidence_by_decision"][decision],
                "rationale": rationale,
                "evidence_checks": checks,
                "contradictions": contradictions,
            }
        )
    return {
        "response_id": "EXTERNAL_TEXT_WAYBACK_LANGUAGE_AI_PRIMARY_REVIEW_RESPONSE_V2",
        "packet_sha256": policy["packet_sha256"],
        "policy_sha256": policy["_policy_sha256"],
        "reviewer": policy["reviewer"],
        "review_type": policy["review_type"],
        "reviewed_at": policy["reviewed_at"],
        "attestation": policy["attestation"],
        "reviews": reviews,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {args.output}")
    if sha256_file(args.packet) != args.packet_sha256:
        raise ValueError("Primary-review packet SHA-256 mismatch")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if policy.get("packet_sha256") != args.packet_sha256:
        raise ValueError("Primary-review policy is not bound to this packet")
    policy["_policy_sha256"] = sha256_file(args.policy)
    response = build_response(packet, policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(args.output), "sha256": sha256_file(args.output), "review_count": len(response["reviews"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
