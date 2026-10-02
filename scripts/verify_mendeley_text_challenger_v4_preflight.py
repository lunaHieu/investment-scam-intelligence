#!/usr/bin/env python3
"""Verify the frozen V4 semantic-challenger preflight without computing embeddings."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import struct
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "configs" / "mendeley_text_challenger_v4_protocol.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"Expected JSON object: {path}")
    return value


def safetensors_summary(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header_bytes_raw = handle.read(8)
        if len(header_bytes_raw) != 8:
            raise AssertionError("Safetensors file is shorter than its length prefix")
        header_bytes = struct.unpack("<Q", header_bytes_raw)[0]
        header = json.loads(handle.read(header_bytes))

    tensors = {name: spec for name, spec in header.items() if name != "__metadata__"}
    if not tensors:
        raise AssertionError("Safetensors header contains no tensors")
    declared_data_bytes = max(spec["data_offsets"][1] for spec in tensors.values())
    expected_file_bytes = 8 + header_bytes + declared_data_bytes
    actual_file_bytes = path.stat().st_size
    return {
        "header_bytes": header_bytes,
        "tensor_count": len(tensors),
        "tensor_dtypes": dict(sorted(Counter(spec["dtype"] for spec in tensors.values()).items())),
        "declared_tensor_data_bytes": declared_data_bytes,
        "expected_file_bytes": expected_file_bytes,
        "actual_file_bytes": actual_file_bytes,
        "structurally_complete": expected_file_bytes == actual_file_bytes,
    }


def validate_protocol_boundaries(protocol: dict[str, Any]) -> None:
    assert protocol["status"] == "FROZEN_BEFORE_EMBEDDING_AND_DEVELOPMENT_TEST_EXTERNAL_UNOPENED"
    assert protocol["encoder_selection_audit"]["candidate_count_after_freeze"] == 1
    assert protocol["encoder"]["fine_tuning_allowed"] is False
    assert protocol["encoder"]["gradient_computation_allowed"] is False
    assert protocol["encoder"]["offline_only"] is True
    assert protocol["text_to_embedding_contract"]["prefix"] == "query: "
    assert protocol["text_to_embedding_contract"]["max_length"] == 512
    assert protocol["text_to_embedding_contract"]["output_dimension"] == 384
    assert protocol["development_design"]["candidate_count"] == 1
    assert protocol["development_design"]["hyperparameter_search"] is False
    assert protocol["development_design"]["threshold_search"] is False
    assert protocol["data_contract"]["development_partition"] == "train"
    assert protocol["data_contract"]["confirmation_partition"] == "validation"
    assert protocol["data_contract"]["internal_test_text_access_allowed"] is False
    assert protocol["data_contract"]["internal_test_label_access_allowed"] is False
    assert protocol["data_contract"]["auxiliary_or_quarantine_access_allowed"] is False
    assert protocol["data_contract"]["existing_external_benchmark_access_allowed"] is False
    assert protocol["safety_contract"]["embedding_operations_before_protocol_freeze"] == 0
    assert protocol["safety_contract"]["model_fit_operations_before_protocol_freeze"] == 0
    assert protocol["safety_contract"]["deployment_allowed"] is False


def validate_local_snapshot(protocol: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    encoder = protocol["encoder"]
    source = manifest["source"]
    assert source["repository"] == encoder["repository"]
    assert source["revision"] == encoder["revision"]
    assert source["license"].lower() == encoder["license"].lower()

    snapshot_root = Path(manifest["local_snapshot"]["root"])
    assert snapshot_root == Path(encoder["local_snapshot_root"])
    assert snapshot_root.is_dir(), f"Missing local snapshot: {snapshot_root}"

    declared = {entry["path"]: entry for entry in manifest["local_snapshot"]["files"]}
    actual = {
        path.relative_to(snapshot_root).as_posix()
        for path in snapshot_root.rglob("*")
        if path.is_file()
    }
    assert not any(path.endswith(".part") for path in actual), "Partial download remains in snapshot"
    assert actual == set(declared), {
        "missing": sorted(set(declared) - actual),
        "undeclared": sorted(actual - set(declared)),
    }

    for relative, expected in declared.items():
        path = snapshot_root / Path(relative)
        assert path.stat().st_size == expected["bytes"], relative
        assert sha256_file(path) == expected["sha256"], relative

    config = read_json(snapshot_root / "config.json")
    sentence_config = read_json(snapshot_root / "sentence_bert_config.json")
    pooling_config = read_json(snapshot_root / "1_Pooling" / "config.json")
    assert config["architectures"] == ["BertModel"]
    assert config["hidden_size"] == 384
    assert config["num_hidden_layers"] == 12
    assert config["max_position_embeddings"] == 512
    assert sentence_config["max_seq_length"] == 512
    assert pooling_config["word_embedding_dimension"] == 384
    assert pooling_config["pooling_mode_mean_tokens"] is True
    assert pooling_config["pooling_mode_cls_token"] is False

    readme = (snapshot_root / "README.md").read_text(encoding="utf-8")
    assert "license: mit" in readme
    assert "Use \"query: \" prefix if you want to use embeddings as features" in readme
    assert "Long texts will be truncated to at most 512 tokens." in readme

    summary = safetensors_summary(snapshot_root / "model.safetensors")
    structural = manifest["structural_verification"]
    structural_key_map = {
        "header_bytes": "safetensors_header_bytes",
        "tensor_count": "tensor_count",
        "tensor_dtypes": "tensor_dtypes",
        "declared_tensor_data_bytes": "declared_tensor_data_bytes",
        "expected_file_bytes": "expected_file_bytes",
        "actual_file_bytes": "actual_file_bytes",
        "structurally_complete": "structurally_complete",
    }
    for summary_key, manifest_key in structural_key_map.items():
        assert summary[summary_key] == structural[manifest_key], summary_key
    assert summary["structurally_complete"] is True
    return {"snapshot_root": str(snapshot_root), **summary}


def validate_pinned_inputs(protocol: dict[str, Any]) -> None:
    manifest_path = REPO_ROOT / protocol["encoder"]["manifest_path"]
    lock_path = REPO_ROOT / protocol["runtime"]["requirements_lock_path"]
    split_path = Path(protocol["data_contract"]["split_path"])
    baseline_path = REPO_ROOT / protocol["data_contract"]["baseline_registry_path"]
    direction_path = REPO_ROOT / protocol["hypothesis_origin"]["registry_path"]

    expected = (
        (manifest_path, protocol["encoder"]["manifest_sha256"]),
        (lock_path, protocol["runtime"]["requirements_lock_sha256"]),
        (split_path, protocol["data_contract"]["split_sha256"]),
        (baseline_path, protocol["data_contract"]["baseline_registry_sha256"]),
        (direction_path, protocol["hypothesis_origin"]["registry_sha256"]),
    )
    for path, checksum in expected:
        assert path.is_file(), f"Missing pinned input: {path}"
        assert sha256_file(path) == checksum, str(path)


def runtime_smoke_test(protocol: dict[str, Any]) -> dict[str, Any]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    import torch
    import tokenizers
    import transformers
    from transformers import AutoConfig, AutoModel, AutoTokenizer

    root = protocol["encoder"]["local_snapshot_root"]
    config = AutoConfig.from_pretrained(root, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True, use_fast=True)
    model = AutoModel.from_pretrained(
        root,
        local_files_only=True,
        use_safetensors=True,
        trust_remote_code=False,
    )
    model.eval()
    model.requires_grad_(False)

    versions = {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "tokenizers": tokenizers.__version__,
        "safetensors": importlib.metadata.version("safetensors"),
        "huggingface_hub": importlib.metadata.version("huggingface-hub"),
        "numpy": importlib.metadata.version("numpy"),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "scipy": importlib.metadata.version("scipy"),
        "joblib": importlib.metadata.version("joblib"),
    }
    assert versions == protocol["runtime"]["primary_packages"]
    assert model.__class__.__name__ == "BertModel"
    assert sum(parameter.numel() for parameter in model.parameters()) == 33360000
    assert all(parameter.requires_grad is False for parameter in model.parameters())
    assert config.hidden_size == 384
    assert config.max_position_embeddings == 512
    assert tokenizer.is_fast is True
    assert tokenizer.truncation_side == "right"
    return {
        "versions": versions,
        "model_loaded": True,
        "all_parameters_frozen": True,
        "forward_passes": 0,
        "embeddings_computed": 0,
    }


def verify(run_runtime_smoke: bool = True) -> dict[str, Any]:
    protocol = read_json(PROTOCOL_PATH)
    validate_protocol_boundaries(protocol)
    validate_pinned_inputs(protocol)
    manifest_path = REPO_ROOT / protocol["encoder"]["manifest_path"]
    manifest = read_json(manifest_path)
    snapshot = validate_local_snapshot(protocol, manifest)
    result: dict[str, Any] = {
        "protocol_id": protocol["protocol_id"],
        "status": "PASS",
        "snapshot": snapshot,
        "runtime_smoke_test": "SKIPPED",
        "embedding_operations": 0,
        "model_fit_operations": 0,
        "model_scoring_operations": 0,
    }
    if run_runtime_smoke:
        result["runtime_smoke_test"] = runtime_smoke_test(protocol)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Verify files and frozen boundaries without importing/loading the model runtime.",
    )
    args = parser.parse_args()
    print(json.dumps(verify(run_runtime_smoke=not args.skip_runtime), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
