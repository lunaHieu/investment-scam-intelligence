"""Validate registry and data-contract files without external dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    registry = load_json(ROOT / "registry" / "sources.json")
    assert isinstance(registry, dict)
    sources = registry["sources"]
    source_ids = [source["source_id"] for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate source_id in registry/sources.json")
    for source in sources:
        if not urlparse(source["url"]).scheme:
            raise ValueError(f"Invalid URL for {source['source_id']}")
        if source["default_evidence_level"] == "SYNTHETIC_ONLY" and source["gold_eligible"]:
            raise ValueError(f"Synthetic source cannot be Gold eligible: {source['source_id']}")
    taxonomy = load_json(ROOT / "registry" / "taxonomy.json")
    codes = [item["code"] for item in taxonomy["subtypes"]]
    if len(codes) != 7 or len(codes) != len(set(codes)):
        raise ValueError("Taxonomy V1 must contain exactly seven unique primary subtypes")
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        schema = load_json(path)
        if not isinstance(schema, dict) or not schema.get("required"):
            raise ValueError(f"Schema must declare required fields: {path.name}")
    readiness = ROOT / "registry" / "source_readiness.md"
    if not readiness.is_file():
        raise ValueError("Missing source readiness audit")
    feature_registries = sorted((ROOT / "registry" / "features").glob("*.json"))
    for path in feature_registries:
        feature_set = load_json(path)
        if feature_set.get("source", {}).get("source_id") not in source_ids:
            raise ValueError(f"Unknown source_id in feature registry: {path.name}")
        contract = feature_set.get("output_contract", {})
        if contract.get("label_fields") != []:
            raise ValueError(f"Feature registry must declare no label fields: {path.name}")
        if contract.get("network_operations") != 0:
            raise ValueError(f"Offline feature registry reports network operations: {path.name}")
        if feature_set.get("training_gate", {}).get("binary_classifier_allowed") is not False:
            raise ValueError(f"Feature set must remain blocked for binary training: {path.name}")
    analysis_registries = sorted((ROOT / "registry" / "analyses").glob("*.json"))
    for path in analysis_registries:
        analysis = load_json(path)
        if analysis.get("source_id") not in source_ids:
            raise ValueError(f"Unknown source_id in analysis registry: {path.name}")
        safety = analysis.get("safety_contract", {})
        if safety.get("network_operations") != 0 or safety.get("labels_created") != 0:
            raise ValueError(f"Analysis must report zero network operations and labels: {path.name}")
        if safety.get("training_allowed") is not False or safety.get("domain_access_allowed") is not False:
            raise ValueError(f"Analysis safety gate is open: {path.name}")
        quality = analysis.get("quality", {})
        if quality.get("mean_adjusted_rand_index_across_seeds", 1.0) < 0.6 and quality.get("stability_assessment") == "HIGH":
            raise ValueError(f"Low-stability clustering cannot be marked HIGH: {path.name}")
    split_registries = sorted((ROOT / "registry" / "splits").glob("*.json"))
    for path in split_registries:
        split = load_json(path)
        if split.get("source", {}).get("source_id") not in source_ids:
            raise ValueError(f"Unknown source_id in split registry: {path.name}")
        if split.get("status") != "FROZEN_DERIVED_SPLIT":
            raise ValueError(f"Split registry must be frozen: {path.name}")
        safety = split.get("safety_contract", {})
        if safety.get("raw_files_modified") is not False:
            raise ValueError(f"Split must preserve raw files: {path.name}")
        if safety.get("network_operations") != 0 or safety.get("source_labels_changed") != 0:
            raise ValueError(f"Split reports network use or label changes: {path.name}")
        if safety.get("model_training_performed") is not False:
            raise ValueError(f"Split construction cannot train a model: {path.name}")
        if split.get("usage_policy", {}).get("external_or_gold_test") is not False:
            raise ValueError(f"Internal split cannot be marked external/Gold: {path.name}")
        roles = {artifact.get("role") for artifact in split.get("artifacts", [])}
        required_roles = {"raw_csv", "derived_split_csv", "split_report", "split_audit"}
        if roles != required_roles:
            raise ValueError(f"Split artifact roles mismatch: {path.name}")
    model_registries = sorted((ROOT / "registry" / "models").glob("*.json"))
    for path in model_registries:
        model = load_json(path)
        if model.get("model_id") == "ISI_FINANCIAL_CLAIMS_ABLATION_V1":
            if model.get("status") != "FROZEN_VALIDATION_SELECTION_RETAIN_TEXT_ONLY_TEST_UNOPENED":
                raise ValueError("Financial Claims ablation must retain text-only with test unopened")
            data_contract = model.get("data_contract", {})
            if data_contract.get("split_version") != "group_split_v2":
                raise ValueError("Financial Claims ablation must use group_split_v2")
            if data_contract.get("test_rows_used") != 0:
                raise ValueError("Financial Claims ablation cannot use test rows")
            if data_contract.get("auxiliary_rows_used") != 0:
                raise ValueError("Financial Claims ablation cannot use auxiliary rows")
            if data_contract.get("quarantine_rows_used") != 0:
                raise ValueError("Financial Claims ablation cannot use quarantine rows")
            decision = model.get("decision", {})
            if decision.get("selected_variant") != "text_only":
                raise ValueError("Failed Financial Claims challenger cannot replace text-only")
            if decision.get("open_internal_test_for_challenger") is not False:
                raise ValueError("Failed Financial Claims challenger cannot open test")
            if model.get("safety_contract", {}).get("deployment_allowed") is not False:
                raise ValueError("Financial Claims ablation deployment gate must remain closed")
            continue
        if model.get("model_id") != "ISI_TEXT_BASELINE_V2":
            continue
        if model.get("status") != "FROZEN_INTERNAL_BASELINE_NOT_FOR_DEPLOYMENT":
            raise ValueError("Text baseline V2 must remain frozen and non-deployable")
        if model.get("data_contract", {}).get("split_version") != "group_split_v2":
            raise ValueError("Text baseline V2 must use group_split_v2")
        if model.get("data_contract", {}).get("auxiliary_rows_used") != 0:
            raise ValueError("Text baseline V2 cannot use auxiliary rows")
        if model.get("data_contract", {}).get("quarantine_rows_used") != 0:
            raise ValueError("Text baseline V2 cannot use quarantine rows")
        if model.get("selection_policy", {}).get("test_used_for_selection") is not False:
            raise ValueError("Text baseline V2 cannot use test for selection")
        if model.get("safety_contract", {}).get("deployment_allowed") is not False:
            raise ValueError("Text baseline V2 deployment gate must remain closed")
    print(
        f"Registry valid: {len(sources)} sources, {len(codes)} taxonomy subtypes, "
        f"{len(feature_registries)} feature registries, {len(analysis_registries)} analysis registries, "
        f"{len(split_registries)} split registries, {len(model_registries)} model/ablation registries, schemas checked."
    )


if __name__ == "__main__":
    main()
