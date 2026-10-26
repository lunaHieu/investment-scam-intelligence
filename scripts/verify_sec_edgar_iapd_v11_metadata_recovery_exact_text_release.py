"""Independently verify the V11 recovery exact-text release gate offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_metadata_recovery_exact_text_release import RELEASE_ID, RESULT_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


QA_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_EXACT_TEXT_RELEASE_INDEPENDENT_QA_V1"


def verify(release_path: Path) -> dict:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("unexpected release identity")
    capture = release.get("inputs", {}).get("capture_qa", {})
    if capture.get("required_status") != RESULT_QA_STATUS:
        errors.append("release is not bound to complete metadata-verified recovery QA")
    decision = release.get("decision", {})
    for key in ("network_access_allowed", "grouping_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
        if decision.get(key) is not False:
            errors.append(f"forbidden gate opened: {key}")
    return {"verification_id": QA_ID, "status": "PASS_V11_METADATA_RECOVERY_EXACT_TEXT_RELEASE" if not errors else "FAIL", "inputs": {"release_sha256": sha256_file(release_path)}, "decision": {"offline_exact_text_extraction_allowed_after_release_qa": not errors, "grouping_allowed": False, "labeling_allowed": False, "training_allowed": False}, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite metadata-recovery exact-text release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
