"""Prepare the offline C2 external-artifact/rights intake template."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import load_object, sha256_file


EXPECTED_PROTOCOL_ID = "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_INTAKE_PROTOCOL_V1"


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def prepare(config_path: Path) -> dict[str, Any]:
    config = load_object(config_path)
    if config.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        raise ValueError("Unexpected C2 intake protocol ID")
    root = config_path.resolve().parents[1]
    for item in config.get("inputs", []):
        path = _resolve(root, str(item["path"]))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Missing or changed C2 input: {item.get('role')}")
    contracts = config.get("source_contracts", [])
    expected = {"cftc_red_list", "dfpi_crypto_scam_tracker", "ssc_vietnam_investor_warnings", "hnx_vietnam_issuer_profiles"}
    if {item.get("source_id") for item in contracts} != expected or len(contracts) != 4:
        raise ValueError("C2 source set differs from the frozen four-source scope")
    template = {
        "template_id": "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_INTAKE_TEMPLATE_V1",
        "instructions": "Copy outside public Git, replace every example value, remove template_id and instructions, set the required pending-QA status, and include one item per immutable file. Never commit protected source bytes, permission contents, personal data, or reviewer identity.",
        "submission_id": "REPLACE_WITH_UNIQUE_SUBMISSION_ID",
        "protocol_id": EXPECTED_PROTOCOL_ID,
        "status": "TEMPLATE_NOT_A_SUBMISSION",
        "created_at": "YYYY-MM-DDTHH:MM:SS+07:00",
        "prepared_by": "REPLACE_WITH_RESEARCHER_ID_OUTSIDE_PUBLIC_GIT",
        "items": [
            {
                "item_id": "REPLACE_WITH_UNIQUE_ITEM_ID",
                "item_type": "SOURCE_ARTIFACT",
                "source_id": "cftc_red_list",
                "official_source_url": "https://www.cftc.gov/LearnAndProtect/Resources/Check/redlist.htm",
                "acquisition_mode": "USER_SUPPLIED_UNTOUCHED_ARTIFACT",
                "acquired_at": "YYYY-MM-DDTHH:MM:SS+07:00",
                "original_filename": "REPLACE_WITH_ORIGINAL_FILENAME",
                "stored_relative_path": "raw/cftc_red_list/YYYY-MM-DD/REPLACE_WITH_FILENAME",
                "media_type": "REPLACE_WITH_MEDIA_TYPE",
                "byte_size": 1,
                "sha256": "replace_with_64_lowercase_hex_characters",
                "rights_basis": {
                    "basis_type": "FIRST_PARTY_PUBLIC_RECORD_INTERNAL_RESEARCH",
                    "terms_or_permission_url": "https://www.cftc.gov/WebPolicy/index.htm",
                    "summary": "Replace with the exact access/reuse basis; this is not a legal conclusion.",
                },
                "prerequisite_rights_registry_path": None,
                "redistribution_permitted": False,
                "contains_personal_data": False,
                "notes": "Reference membership never creates an automatic label.",
            }
        ],
    }
    return {"config": config, "template": template}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_no_overwrite(path: Path, payload: bytes) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() or partial.exists():
        raise FileExistsError(f"Refusing to overwrite C2 output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(payload)
    partial.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.config)
    outputs = result["config"]["planned_outputs"]
    for key in ("completed_submission", "independent_submission_qa", "versioned_readiness_ledger"):
        path = Path(outputs[key])
        if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
            raise FileExistsError(f"Future C2 output already exists: {path}")
    template_bytes = _json_bytes(result["template"])
    report = {
        "report_id": "ISI_TARGET_TEXT_CORPUS_V1_C2_EXTERNAL_ARTIFACT_INTAKE_PREPARATION_REPORT_V1",
        "status": "PASS_C2_INTAKE_TEMPLATE_PREPARED_EXTERNAL_INPUTS_ABSENT",
        "protocol_sha256": sha256_file(args.config),
        "template_sha256": hashlib.sha256(template_bytes).hexdigest(),
        "source_contracts": 4,
        "source_artifact_channels_open_for_qa": ["cftc_red_list", "dfpi_crypto_scam_tracker"],
        "rights_record_only_channels": ["hnx_vietnam_issuer_profiles", "ssc_vietnam_investor_warnings"],
        "decision": {"tooling_ready": True, "completed_submission_exists": False, "source_files_acquired": 0, "rights_records_acquired": 0, "training_allowed": False},
        "safety_contract": {"network_operations": 0, "candidate_records_enumerated": 0, "labels_changed": 0, "model_operations": 0},
    }
    _write_no_overwrite(Path(outputs["submission_template"]), template_bytes)
    _write_no_overwrite(Path(outputs["preparation_report"]), _json_bytes(report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
