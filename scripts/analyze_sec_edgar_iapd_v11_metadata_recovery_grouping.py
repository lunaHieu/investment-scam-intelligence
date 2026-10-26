"""Run V11 recovery grouping with the frozen V1 grouping algorithm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.analyze_sec_edgar_iapd_post_capture_grouping_v1 as frozen_v1
from scripts.build_sec_edgar_iapd_v11_metadata_recovery_grouping_release import RELEASE_ID
from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_grouping_release import PASS_STATUS as RELEASE_QA_STATUS
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object


ANALYSIS_ID = "ISI_SEC_EDGAR_IAPD_V11_METADATA_RECOVERY_EXCLUSION_GROUPING_V1"


def build(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    original_release_id = frozen_v1.RELEASE_ID
    original_qa_status = frozen_v1.RELEASE_QA_STATUS
    frozen_v1.RELEASE_ID = RELEASE_ID
    frozen_v1.RELEASE_QA_STATUS = RELEASE_QA_STATUS
    try:
        result = frozen_v1.build(release_path, release_qa_path)
    finally:
        frozen_v1.RELEASE_ID = original_release_id
        frozen_v1.RELEASE_QA_STATUS = original_qa_status
    result["analysis_id"] = ANALYSIS_ID
    result["population_contract"] = load_object(release_path)["population_contract"]
    return result


def execute(release_path: Path, release_qa_path: Path) -> dict[str, Any]:
    release = load_object(release_path)
    output = Path(str(release["output"]["path"]))
    if output.exists() or output.with_suffix(output.suffix + ".partial").exists():
        raise FileExistsError("Refusing to overwrite recovery grouping analysis")
    result = build(release_path, release_qa_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    partial.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-qa", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.release, args.release_qa)
    print(json.dumps({"analysis_id": result["analysis_id"], "status": result["status"], "counts": result["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
