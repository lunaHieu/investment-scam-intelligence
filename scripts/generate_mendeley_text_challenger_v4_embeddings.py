"""Generate the frozen V4 E5 embeddings offline for group_split_v2 train only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mendeley_text_baseline_v2_common import (  # noqa: E402
    EXPECTED_PARTITION_COUNTS,
    EXPECTED_SOURCES,
    EXPECTED_SPLIT_SHA256,
    _validate_header,
    _validate_routing_row,
    sha256_file,
)


PROTOCOL_ID = "MENDELEY_TEXT_CHALLENGER_V4_FROZEN_E5_LINEAR_PROTOCOL"
EXPECTED_PROTOCOL_SHA256 = "2513ac96d5d209a1e04adedd30da5ab78e31146cd0e6962d77a6939cd6d75b77"
EXPECTED_REVISION = "ffb93f3bd4047442299a41ebb6fa998a38507c52"
EXPECTED_WEIGHT_SHA256 = "45bfa60070649aae2244fbc9d508537779b93b6f353c17b0f95ceccb1c5116c1"
EXPECTED_TOKENIZER_SHA256 = "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def validate_protocol(protocol_path: Path, split_path: Path) -> dict[str, Any]:
    if sha256_file(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("V4 protocol changed after it was frozen")
    protocol = load_json(protocol_path)
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Unexpected V4 protocol ID")
    if protocol.get("status") != "FROZEN_BEFORE_EMBEDDING_AND_DEVELOPMENT_TEST_EXTERNAL_UNOPENED":
        raise ValueError("V4 protocol is not frozen before embeddings")
    if sha256_file(split_path) != EXPECTED_SPLIT_SHA256:
        raise ValueError("group_split_v2 SHA-256 mismatch")
    data = protocol.get("data_contract", {})
    if data.get("split_sha256") != EXPECTED_SPLIT_SHA256:
        raise ValueError("Protocol split SHA-256 mismatch")
    if data.get("development_partition") != "train":
        raise ValueError("Only the train partition may be embedded in development")
    for key in (
        "internal_test_text_access_allowed",
        "internal_test_label_access_allowed",
        "auxiliary_or_quarantine_access_allowed",
        "existing_external_benchmark_access_allowed",
    ):
        if data.get(key) is not False:
            raise ValueError(f"Protocol opens prohibited access: {key}")
    encoder = protocol.get("encoder", {})
    if encoder.get("revision") != EXPECTED_REVISION:
        raise ValueError("Unexpected encoder revision")
    if encoder.get("weight_sha256") != EXPECTED_WEIGHT_SHA256:
        raise ValueError("Unexpected encoder weight checksum")
    if encoder.get("offline_only") is not True or encoder.get("fine_tuning_allowed") is not False:
        raise ValueError("Encoder must remain offline and frozen")
    contract = protocol.get("text_to_embedding_contract", {})
    expected_contract = {
        "prefix": "query: ",
        "max_length": 512,
        "truncation": True,
        "truncation_side": "right",
        "batch_size": 16,
        "output_dimension": 384,
        "output_dtype": "float32",
    }
    for key, expected in expected_contract.items():
        if contract.get(key) != expected:
            raise ValueError(f"Unexpected embedding contract field: {key}")
    return protocol


def read_train_only(path: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Scan routing but retain and validate labels/text only for train rows."""

    counts: Counter[str] = Counter()
    train_rows: list[dict[str, str]] = []
    train_ids: set[str] = set()
    train_groups: set[str] = set()
    all_ids: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(reader.fieldnames)
        for row in reader:
            record_id = row["record_id"]
            if record_id in all_ids:
                raise ValueError(f"Duplicate record_id: {record_id}")
            all_ids.add(record_id)
            partition = row["partition"]
            counts[partition] += 1
            _validate_routing_row(row, validate_benchmark_label=partition == "train")
            if partition != "train":
                continue
            if record_id in train_ids:
                raise ValueError(f"Duplicate train record_id: {record_id}")
            if not row["text_content"].strip():
                raise ValueError(f"Empty train text: {record_id}")
            train_ids.add(record_id)
            train_groups.add(row["split_group_id"])
            train_rows.append({
                "record_id": record_id,
                "source_dataset": row["source_dataset"],
                "text_content": row["text_content"],
                "label": row["label"],
                "partition": "train",
                "split_group_id": row["split_group_id"],
            })
    if dict(counts) != EXPECTED_PARTITION_COUNTS:
        raise ValueError(f"Partition counts mismatch: {dict(counts)}")
    if len(train_rows) != EXPECTED_PARTITION_COUNTS["train"]:
        raise ValueError("Train row count mismatch")
    if {row["source_dataset"] for row in train_rows} != EXPECTED_SOURCES:
        raise ValueError("Train rows do not contain the four expected sources")
    train_rows.sort(key=lambda row: row["record_id"])
    return train_rows, {
        "partition_counts_scanned": dict(counts),
        "train_rows_retained": len(train_rows),
        "train_groups_retained": len(train_groups),
        "validation_text_rows_retained": 0,
        "validation_labels_accessed": 0,
        "test_text_rows_retained": 0,
        "test_labels_accessed": 0,
        "auxiliary_text_rows_retained": 0,
        "quarantine_text_rows_retained": 0,
    }


def ordered_input_digest(rows: list[dict[str, str]], prefix: str) -> str:
    digest = hashlib.sha256()
    for row in rows:
        payload = json.dumps(
            [row["record_id"], prefix + row["text_content"]],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def cache_key(protocol: dict[str, Any], partition: str, input_digest: str) -> dict[str, Any]:
    encoder = protocol["encoder"]
    representation = protocol["text_to_embedding_contract"]
    return {
        "split_sha256": protocol["data_contract"]["split_sha256"],
        "partition": partition,
        "ordered_record_id_and_prefixed_text_sha256": input_digest,
        "encoder_revision": encoder["revision"],
        "weight_sha256": encoder["weight_sha256"],
        "tokenizer_json_sha256": EXPECTED_TOKENIZER_SHA256,
        "prefix": representation["prefix"],
        "max_length": representation["max_length"],
        "pooling": representation["pooling"],
        "normalization": representation["normalization"],
        "runtime_lock_sha256": protocol["runtime"]["requirements_lock_sha256"],
    }


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepare_outputs(output_dir: Path) -> tuple[Path, Path]:
    embeddings_path = output_dir / "train_e5_small_v2_ffb93f3b_embeddings.npz"
    metadata_path = output_dir / "train_e5_small_v2_ffb93f3b_metadata.json"
    for path in (embeddings_path, metadata_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen embedding output: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return embeddings_path, metadata_path


def token_length_report(rows: list[dict[str, str]], lengths: np.ndarray) -> dict[str, Any]:
    if len(rows) != len(lengths):
        raise ValueError("Token length count mismatch")
    grouped: dict[str, list[int]] = defaultdict(list)
    grouped["__all__"] = []
    for row, length in zip(rows, lengths):
        grouped["__all__"].append(int(length))
        grouped[row["source_dataset"]].append(int(length))
    report = {}
    for source, values in sorted(grouped.items()):
        array = np.asarray(values, dtype=np.int64)
        report[source] = {
            "partition": "train",
            "source_dataset": None if source == "__all__" else source,
            "row_count": int(len(array)),
            "truncated_count": int(np.sum(array > 512)),
            "truncated_rate": round(float(np.mean(array > 512)), 6),
            "pre_truncation_token_p50": round(float(np.quantile(array, 0.50)), 3),
            "pre_truncation_token_p95": round(float(np.quantile(array, 0.95)), 3),
            "pre_truncation_token_max": int(array.max()),
        }
    return report


def compute_embeddings(
    rows: list[dict[str, str]], protocol: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoTokenizer

    encoder = protocol["encoder"]
    contract = protocol["text_to_embedding_contract"]
    snapshot = Path(encoder["local_snapshot_root"])
    if sha256_file(snapshot / "model.safetensors") != encoder["weight_sha256"]:
        raise ValueError("Local encoder weight SHA-256 mismatch")
    if sha256_file(snapshot / "tokenizer.json") != EXPECTED_TOKENIZER_SHA256:
        raise ValueError("Local tokenizer SHA-256 mismatch")

    tokenizer = AutoTokenizer.from_pretrained(
        snapshot,
        local_files_only=True,
        use_fast=True,
        trust_remote_code=False,
    )
    tokenizer.truncation_side = contract["truncation_side"]
    model = AutoModel.from_pretrained(
        snapshot,
        local_files_only=True,
        use_safetensors=True,
        trust_remote_code=False,
    )
    model.eval()
    model.requires_grad_(False)
    model.to("cpu")

    thread_count = max(1, min(8, os.cpu_count() or 1))
    torch.set_num_threads(thread_count)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    prefixed = [contract["prefix"] + row["text_content"] for row in rows]
    length_values: list[int] = []
    length_batch_size = 128
    for start in range(0, len(prefixed), length_batch_size):
        batch = tokenizer(
            prefixed[start : start + length_batch_size],
            add_special_tokens=True,
            truncation=False,
            padding=False,
            return_length=True,
        )
        length_values.extend(int(value) for value in batch["length"])
    lengths = np.asarray(length_values, dtype=np.int64)

    batch_size = int(contract["batch_size"])
    result = np.empty((len(rows), int(contract["output_dimension"])), dtype=np.float32)
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(prefixed), batch_size):
            stop = min(start + batch_size, len(prefixed))
            encoded = tokenizer(
                prefixed[start:stop],
                add_special_tokens=True,
                max_length=int(contract["max_length"]),
                truncation=True,
                padding=True,
                return_tensors="pt",
            )
            output = model(**encoded)
            mask = encoded["attention_mask"]
            hidden = output.last_hidden_state.masked_fill(~mask[..., None].bool(), 0.0)
            pooled = hidden.sum(dim=1) / mask.sum(dim=1)[..., None]
            normalized = functional.normalize(pooled, p=2, dim=1)
            result[start:stop] = normalized.cpu().numpy().astype(np.float32, copy=False)
            if stop == len(prefixed) or stop % 128 == 0:
                elapsed = time.perf_counter() - started
                print(
                    json.dumps({
                        "event": "embedding_progress",
                        "completed": stop,
                        "total": len(prefixed),
                        "elapsed_seconds": round(elapsed, 1),
                    }),
                    flush=True,
                )
    elapsed = time.perf_counter() - started
    if not np.isfinite(result).all():
        raise ValueError("Embedding matrix contains a non-finite value")
    norms = np.linalg.norm(result, axis=1)
    maximum_norm_error = float(np.max(np.abs(norms - 1.0)))
    if maximum_norm_error > 1e-5:
        raise ValueError(f"Embedding L2 norm error too large: {maximum_norm_error}")
    runtime = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": __import__("transformers").__version__,
        "tokenizers": __import__("tokenizers").__version__,
        "device": "cpu",
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "elapsed_seconds": round(elapsed, 3),
        "forward_batches": int((len(rows) + batch_size - 1) // batch_size),
        "network_operations": 0,
    }
    return result, lengths, {
        "runtime": runtime,
        "maximum_l2_norm_error": maximum_norm_error,
        "all_values_finite": True,
        "all_parameters_frozen": all(not parameter.requires_grad for parameter in model.parameters()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()

    protocol = validate_protocol(args.protocol, args.input)
    embeddings_path, metadata_path = prepare_outputs(args.output_dir)
    rows, access = read_train_only(args.input)
    prefix = protocol["text_to_embedding_contract"]["prefix"]
    input_digest = ordered_input_digest(rows, prefix)
    key = cache_key(protocol, "train", input_digest)
    key_digest = canonical_digest(key)
    embeddings, token_lengths, diagnostics = compute_embeddings(rows, protocol)

    temporary_embeddings = embeddings_path.with_suffix(".npz.part")
    with temporary_embeddings.open("wb") as handle:
        np.savez_compressed(
            handle,
            record_id=np.asarray([row["record_id"] for row in rows], dtype=str),
            embedding=embeddings,
        )
    temporary_embeddings.replace(embeddings_path)

    metadata = {
        "artifact_id": "MENDELEY_TEXT_CHALLENGER_V4_TRAIN_E5_EMBEDDINGS",
        "created_at": args.run_at,
        "status": "FROZEN_TRAIN_ONLY_EMBEDDINGS_VALIDATED",
        "protocol": {
            "path": str(args.protocol),
            "sha256": sha256_file(args.protocol),
            "protocol_id": PROTOCOL_ID,
        },
        "input": {
            "path": str(args.input),
            "sha256": sha256_file(args.input),
            "partition": "train",
            "row_count": len(rows),
            "record_id_order": "ascending",
            "ordered_record_id_and_prefixed_text_sha256": input_digest,
            "access": access,
        },
        "cache_key": key,
        "cache_key_sha256": key_digest,
        "encoder": {
            "repository": protocol["encoder"]["repository"],
            "revision": protocol["encoder"]["revision"],
            "weight_sha256": protocol["encoder"]["weight_sha256"],
            "fine_tuned": False,
        },
        "representation": protocol["text_to_embedding_contract"],
        "matrix": {
            "shape": list(embeddings.shape),
            "dtype": str(embeddings.dtype),
            "all_values_finite": diagnostics["all_values_finite"],
            "maximum_l2_norm_error": round(diagnostics["maximum_l2_norm_error"], 10),
        },
        "truncation_report": token_length_report(rows, token_lengths),
        "runtime": diagnostics["runtime"],
        "quality_gates": {
            "protocol_hash_verified": True,
            "split_hash_verified": True,
            "train_rows_exact": len(rows) == 3916,
            "record_ids_unique": len({row["record_id"] for row in rows}) == len(rows),
            "record_ids_sorted": [row["record_id"] for row in rows]
            == sorted(row["record_id"] for row in rows),
            "shape_exact": embeddings.shape == (3916, 384),
            "dtype_float32": embeddings.dtype == np.float32,
            "all_values_finite": diagnostics["all_values_finite"],
            "l2_norm_within_tolerance": diagnostics["maximum_l2_norm_error"] <= 1e-5,
            "all_encoder_parameters_frozen": diagnostics["all_parameters_frozen"],
            "validation_text_rows_retained_zero": access["validation_text_rows_retained"] == 0,
            "validation_labels_accessed_zero": access["validation_labels_accessed"] == 0,
            "test_text_rows_retained_zero": access["test_text_rows_retained"] == 0,
            "test_labels_accessed_zero": access["test_labels_accessed"] == 0,
        },
        "safety_contract": {
            "partition_embedded": "train",
            "validation_embedding_operations": 0,
            "test_embedding_operations": 0,
            "external_embedding_operations": 0,
            "classifier_fit_operations": 0,
            "model_scoring_operations": 0,
            "source_labels_changed": 0,
            "raw_files_modified": False,
            "split_file_modified": False,
            "deployment_allowed": False,
        },
        "artifacts": {
            "embedding_cache": {
                "path": str(embeddings_path),
                "sha256": sha256_file(embeddings_path),
                "bytes": embeddings_path.stat().st_size,
            }
        },
    }
    failed = [name for name, passed in metadata["quality_gates"].items() if not passed]
    if failed:
        raise ValueError("Embedding quality gates failed: " + ", ".join(failed))
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "metadata": str(metadata_path),
        "metadata_sha256": sha256_file(metadata_path),
        "embeddings": str(embeddings_path),
        "embeddings_sha256": sha256_file(embeddings_path),
        "matrix_shape": list(embeddings.shape),
        "truncated_rows": metadata["truncation_report"]["__all__"]["truncated_count"],
        "elapsed_seconds": diagnostics["runtime"]["elapsed_seconds"],
        "validation_opened": False,
        "test_opened": False,
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
