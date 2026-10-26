"""Independently verify the V11 supplemental exact-text release gate offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_supplemental_exact_text_release import RELEASE_ID, STRICT_CAPTURE_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


QA_ID = "ISI_SEC_EDGAR_IAPD_V11_SUPPLEMENTAL_EXACT_TEXT_RELEASE_INDEPENDENT_QA_V1"


def verify(release_path: Path) -> dict:
    release = load_object(release_path)
    errors: list[str] = []
    if release.get("release_id") != RELEASE_ID:
        errors.append("unexpected release identity")
    capture = release.get("inputs", {}).get("capture_qa", {})
    if capture.get("required_status") != STRICT_CAPTURE_QA_STATUS:
        errors.append("release is not bound to strict capture QA")
    decision = release.get("decision", {})
    if decision.get("network_access_allowed") is not False or decision.get("labeling_allowed") is not False or decision.get("training_allowed") is not False:
        errors.append("forbidden gate opened")
    return {"verification_id": QA_ID, "status": "PASS_V11_SUPPLEMENTAL_EXACT_TEXT_RELEASE" if not errors else "FAIL", "inputs": {"release_sha256": sha256_file(release_path)}, "decision": {"offline_exact_text_extraction_allowed_after_release_qa": not errors, "grouping_allowed": False, "labeling_allowed": False, "training_allowed": False}, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite supplemental exact-text release QA")
    result = verify(args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".partial")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
