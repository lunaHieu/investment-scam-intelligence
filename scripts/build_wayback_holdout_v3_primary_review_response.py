"""Expand the explicit V3 case roster into a hash-bound primary-review response."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_wayback_language_primary_review_response_v2 import build_response
from src.isi.normalization.external_references import sha256_file


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
    if packet.get("packet_id") != "EXTERNAL_TEXT_WAYBACK_HOLDOUT_PRIMARY_REVIEW_V3":
        raise ValueError("Unexpected V3 primary-review packet ID")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if policy.get("packet_sha256") != args.packet_sha256:
        raise ValueError("Primary-review policy is not bound to this packet")
    policy["_policy_sha256"] = sha256_file(args.policy)
    response = build_response(packet, policy)
    response["response_id"] = "EXTERNAL_TEXT_WAYBACK_HOLDOUT_AI_PRIMARY_REVIEW_RESPONSE_V3"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(args.output), "sha256": sha256_file(args.output), "review_count": len(response["reviews"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
