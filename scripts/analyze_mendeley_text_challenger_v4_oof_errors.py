"""Analyze frozen V4 OOF errors on train only without fitting or scoring a model."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_mendeley_text_challenger_v4_embeddings import (  # noqa: E402
    EXPECTED_TOKENIZER_SHA256,
    load_json,
    read_train_only,
)
from mendeley_text_baseline_v2_common import sha256_file  # noqa: E402
from verify_mendeley_text_challenger_v4_development import load_jsonl  # noqa: E402


PROTOCOL_ID = "MENDELEY_TEXT_CHALLENGER_V4_TRAIN_OOF_ERROR_ANALYSIS"
ANALYSIS_ID = "MENDELEY_TEXT_CHALLENGER_V4_TRAIN_OOF_ERROR_ANALYSIS_RESULT"
EXPECTED_PROTOCOL_SHA256 = "46deee65e3a12ea1d2de6927863ef8aaad718541954f8d34702eb8a1dff3e4b4"
EXPECTED_MODEL_PROTOCOL_SHA256 = "2513ac96d5d209a1e04adedd30da5ab78e31146cd0e6962d77a6939cd6d75b77"
EXPECTED_STATUS = "DEVELOPMENT_CHALLENGER_REJECTED_VALIDATION_TEST_EXTERNAL_UNOPENED"

EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
LONG_ID_RE = re.compile(
    r"\b(?=[A-Za-z0-9]{26,64}\b)(?=[A-Za-z0-9]*[A-Za-z])"
    r"(?=[A-Za-z0-9]*\d)[A-Za-z0-9]+\b"
)


def redact_excerpt(text: str, limit: int = 240) -> str:
    value = EMAIL_RE.sub("[EMAIL]", text)
    value = URL_RE.sub("[URL]", value)
    value = PHONE_RE.sub("[PHONE]", value)
    value = LONG_ID_RE.sub("[LONG_ID]", value)
    value = " ".join(value.split())
    return value[:limit].rstrip()


def validate_protocol(protocol_path: Path) -> dict[str, Any]:
    if sha256_file(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("OOF error-analysis protocol changed after freeze")
    protocol = load_json(protocol_path)
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Unexpected error-analysis protocol ID")
    if protocol.get("status") != "LOCKED_BEFORE_ROW_LEVEL_DIAGNOSTIC":
        raise ValueError("Error-analysis protocol is not locked")
    scope = protocol.get("scope", {})
    if scope.get("partition") != "train" or scope.get("expected_rows") != 3916:
        raise ValueError("Unexpected analysis scope")
    prohibited_false = (
        "validation_text_access_allowed",
        "validation_label_access_allowed",
        "test_access_allowed",
        "auxiliary_or_quarantine_access_allowed",
        "external_benchmark_access_allowed",
        "new_embedding_computation_allowed",
        "model_fit_allowed",
        "model_scoring_allowed",
    )
    if any(scope.get(key) is not False for key in prohibited_false):
        raise ValueError("Protocol opens a prohibited diagnostic operation")
    for item in protocol.get("inputs", []):
        path = Path(item["path"])
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Pinned analysis input missing or changed: {item['role']}")
    return protocol


def token_bucket(length: int) -> str:
    if length <= 32:
        return "le_32"
    if length <= 128:
        return "33_128"
    if length <= 512:
        return "129_512"
    return "gt_512"


def transition(label: int, baseline_prediction: int, challenger_prediction: int) -> str:
    baseline_correct = baseline_prediction == label
    challenger_correct = challenger_prediction == label
    if baseline_correct and challenger_correct:
        return "both_correct"
    if baseline_correct and not challenger_correct:
        return "e5_regression"
    if not baseline_correct and challenger_correct:
        return "e5_recovery"
    return "both_wrong"


def prediction_confidence(score: float, prediction: int) -> float:
    if not 0.0 <= score <= 1.0 or prediction not in (0, 1):
        raise ValueError("Invalid stored prediction or probability")
    return score if prediction == 1 else 1.0 - score


def measure_token_lengths(
    rows: list[dict[str, str]], model_protocol: dict[str, Any]
) -> np.ndarray:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from transformers import AutoTokenizer

    snapshot = Path(model_protocol["encoder"]["local_snapshot_root"])
    if sha256_file(snapshot / "tokenizer.json") != EXPECTED_TOKENIZER_SHA256:
        raise ValueError("Pinned tokenizer checksum mismatch")
    tokenizer = AutoTokenizer.from_pretrained(
        snapshot,
        local_files_only=True,
        use_fast=True,
        trust_remote_code=False,
    )
    tokenizer.model_max_length = 1_000_000_000
    prefix = model_protocol["text_to_embedding_contract"]["prefix"]
    values: list[int] = []
    for start in range(0, len(rows), 128):
        encoded = tokenizer(
            [prefix + row["text_content"] for row in rows[start : start + 128]],
            add_special_tokens=True,
            padding=False,
            truncation=False,
            return_length=True,
        )
        values.extend(int(value) for value in encoded["length"])
    result = np.asarray(values, dtype=np.int64)
    if result.shape != (3916,) or np.any(result <= 0):
        raise ValueError("Unexpected token-length vector")
    return result


def nearest_neighbors(
    embeddings: np.ndarray,
    rows: list[dict[str, Any]],
    *,
    block_rows: int,
) -> tuple[np.ndarray, np.ndarray]:
    if embeddings.shape != (len(rows), 384):
        raise ValueError(f"Unexpected embedding shape: {embeddings.shape}")
    if not np.isfinite(embeddings).all():
        raise ValueError("Embedding matrix contains a non-finite value")
    ids = [str(row["record_id"]) for row in rows]
    if ids != sorted(ids):
        raise ValueError("Rows must be sorted by record_id for deterministic tie breaking")
    group_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        group_indices[str(row["split_group_id"])].append(index)
    nearest_index = np.empty(len(rows), dtype=np.int64)
    nearest_similarity = np.empty(len(rows), dtype=np.float32)
    for start in range(0, len(rows), block_rows):
        stop = min(start + block_rows, len(rows))
        similarities = embeddings[start:stop] @ embeddings.T
        for local_index, global_index in enumerate(range(start, stop)):
            similarities[local_index, group_indices[str(rows[global_index]["split_group_id"])]] = -np.inf
        selected = np.argmax(similarities, axis=1)
        nearest_index[start:stop] = selected
        nearest_similarity[start:stop] = similarities[np.arange(stop - start), selected]
    if np.any(~np.isfinite(nearest_similarity)):
        raise ValueError("A row has no eligible nearest neighbor")
    return nearest_index, nearest_similarity


def rate_summary(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(records)
    count = len(items)
    transitions = Counter(item["transition"] for item in items)
    baseline_errors = transitions["e5_recovery"] + transitions["both_wrong"]
    challenger_errors = transitions["e5_regression"] + transitions["both_wrong"]

    def rate(value: int) -> float | None:
        return None if count == 0 else round(value / count, 6)

    return {
        "row_count": count,
        "transition_counts": {
            name: transitions[name]
            for name in ("both_correct", "e5_regression", "e5_recovery", "both_wrong")
        },
        "baseline_error_count": baseline_errors,
        "baseline_error_rate": rate(baseline_errors),
        "challenger_error_count": challenger_errors,
        "challenger_error_rate": rate(challenger_errors),
        "e5_regression_rate": rate(transitions["e5_regression"]),
        "e5_recovery_rate": rate(transitions["e5_recovery"]),
        "net_e5_regression_rate": rate(
            transitions["e5_regression"] - transitions["e5_recovery"]
        ),
    }


def grouped_rate_summary(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record[key])].append(record)
    return {name: rate_summary(grouped[name]) for name in sorted(grouped)}


def neighbor_summary(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(records)
    if not items:
        return {
            "row_count": 0,
            "same_source_rate": None,
            "same_label_rate": None,
            "same_source_and_label_rate": None,
            "similarity_mean": None,
            "similarity_p50": None,
            "similarity_p95": None,
        }
    similarities = np.asarray(
        [record["nearest_neighbor_similarity"] for record in items], dtype=np.float64
    )
    return {
        "row_count": len(items),
        "same_source_rate": round(
            float(np.mean([record["nearest_neighbor_same_source"] for record in items])), 6
        ),
        "same_label_rate": round(
            float(np.mean([record["nearest_neighbor_same_label"] for record in items])), 6
        ),
        "same_source_and_label_rate": round(
            float(
                np.mean(
                    [
                        record["nearest_neighbor_same_source"]
                        and record["nearest_neighbor_same_label"]
                        for record in items
                    ]
                )
            ),
            6,
        ),
        "similarity_mean": round(float(np.mean(similarities)), 6),
        "similarity_p50": round(float(np.quantile(similarities, 0.50)), 6),
        "similarity_p95": round(float(np.quantile(similarities, 0.95)), 6),
    }


def review_queue(
    records: list[dict[str, Any]], protocol: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    policy = protocol["review_queue"]
    limit = int(policy["maximum_records_per_source_per_category"])
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for category in policy["categories"]:
        for source in sorted({record["source_dataset"] for record in records}):
            candidates = [
                record
                for record in records
                if record["transition"] == category and record["source_dataset"] == source
            ]
            candidates.sort(
                key=lambda record: (
                    -record["challenger_prediction_confidence"],
                    record["record_id"],
                )
            )
            used_groups: set[str] = set()
            chosen = []
            for record in candidates:
                if record["split_group_id"] in used_groups:
                    continue
                used_groups.add(record["split_group_id"])
                chosen.append(record)
                if len(chosen) == limit:
                    break
            counts[f"{category}|{source}"] = len(chosen)
            for record in chosen:
                selected.append({
                    "record_id": record["record_id"],
                    "source_dataset": record["source_dataset"],
                    "source_label": record["source_label"],
                    "development_fold": record["development_fold"],
                    "split_group_id": record["split_group_id"],
                    "transition": record["transition"],
                    "pre_truncation_token_count": record["pre_truncation_token_count"],
                    "pre_truncation_token_bucket": record["pre_truncation_token_bucket"],
                    "truncated_at_512": record["truncated_at_512"],
                    "baseline_prediction": record["baseline_prediction"],
                    "baseline_score_label_1": record["baseline_score_label_1"],
                    "challenger_prediction": record["challenger_prediction"],
                    "challenger_score_label_1": record["challenger_score_label_1"],
                    "challenger_prediction_confidence": record[
                        "challenger_prediction_confidence"
                    ],
                    "nearest_neighbor_record_id": record["nearest_neighbor_record_id"],
                    "nearest_neighbor_source_dataset": record[
                        "nearest_neighbor_source_dataset"
                    ],
                    "nearest_neighbor_source_label": record[
                        "nearest_neighbor_source_label"
                    ],
                    "nearest_neighbor_similarity": record[
                        "nearest_neighbor_similarity"
                    ],
                    "nearest_neighbor_same_source": record[
                        "nearest_neighbor_same_source"
                    ],
                    "nearest_neighbor_same_label": record[
                        "nearest_neighbor_same_label"
                    ],
                    "redacted_text_excerpt": record["redacted_text_excerpt"],
                    "review_purpose": "qualitative diagnostic only; no relabeling or tuning",
                })
    selected.sort(key=lambda record: (
        record["transition"], record["source_dataset"],
        -record["challenger_prediction_confidence"], record["record_id"]
    ))
    return selected, dict(sorted(counts.items()))


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def prepare_outputs(output_dir: Path) -> dict[str, Path]:
    paths = {
        "report": output_dir / "text_challenger_v4_train_oof_error_analysis.json",
        "row_diagnostics": output_dir / "text_challenger_v4_train_oof_row_diagnostics.jsonl",
        "review_queue": output_dir / "text_challenger_v4_train_oof_review_queue.jsonl",
    }
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite frozen error-analysis output: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--embedding-metadata", type=Path, required=True)
    parser.add_argument("--development-result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-at", required=True)
    args = parser.parse_args()

    protocol = validate_protocol(args.protocol)
    if sha256_file(args.model_protocol) != EXPECTED_MODEL_PROTOCOL_SHA256:
        raise ValueError("Frozen model protocol checksum mismatch")
    model_protocol = load_json(args.model_protocol)
    result = load_json(args.development_result)
    if result.get("status") != EXPECTED_STATUS:
        raise ValueError("Development result is not the frozen rejected OOF result")
    decision = result.get("decision", {})
    if decision.get("all_gates_passed") is not False or decision.get(
        "validation_opened"
    ) is not False:
        raise ValueError("Development result does not keep validation closed")

    paths = prepare_outputs(args.output_dir)
    rows, access = read_train_only(args.input)
    row_by_id = {row["record_id"]: row for row in rows}
    predictions = load_jsonl(args.predictions)
    if len(predictions) != 3916 or len({row["record_id"] for row in predictions}) != 3916:
        raise ValueError("Expected 3,916 unique OOF prediction rows")
    prediction_by_id = {row["record_id"]: row for row in predictions}
    if set(prediction_by_id) != set(row_by_id):
        raise ValueError("OOF predictions do not cover train records exactly")

    embedding_metadata = load_json(args.embedding_metadata)
    if sha256_file(args.embeddings) != embedding_metadata["artifacts"]["embedding_cache"][
        "sha256"
    ]:
        raise ValueError("Embedding cache checksum mismatch")
    with np.load(args.embeddings, allow_pickle=False) as cache:
        embedding_ids = cache["record_id"].astype(str)
        embeddings = cache["embedding"].astype(np.float32, copy=False)
    expected_ids = np.asarray([row["record_id"] for row in rows], dtype=str)
    if not np.array_equal(embedding_ids, expected_ids):
        raise ValueError("Embedding cache order does not match sorted train records")

    token_lengths = measure_token_lengths(rows, model_protocol)
    neighbor_index, neighbor_similarity = nearest_neighbors(
        embeddings,
        rows,
        block_rows=int(protocol["nearest_neighbor_diagnostic"]["block_rows"]),
    )

    diagnostic_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        prediction = prediction_by_id[row["record_id"]]
        label = int(row["label"])
        baseline_prediction = int(prediction["baseline_prediction"])
        challenger_prediction = int(prediction["challenger_prediction"])
        baseline_score = float(prediction["baseline_score_label_1"])
        challenger_score = float(prediction["challenger_score_label_1"])
        neighbor = rows[int(neighbor_index[index])]
        token_count = int(token_lengths[index])
        diagnostic_rows.append({
            "record_id": row["record_id"],
            "source_dataset": row["source_dataset"],
            "source_label": label,
            "development_fold": int(prediction["development_fold"]),
            "split_group_id": row["split_group_id"],
            "transition": transition(label, baseline_prediction, challenger_prediction),
            "pre_truncation_token_count": token_count,
            "pre_truncation_token_bucket": token_bucket(token_count),
            "truncated_at_512": token_count > 512,
            "baseline_prediction": baseline_prediction,
            "baseline_score_label_1": round(baseline_score, 10),
            "baseline_prediction_confidence": round(
                prediction_confidence(baseline_score, baseline_prediction), 10
            ),
            "challenger_prediction": challenger_prediction,
            "challenger_score_label_1": round(challenger_score, 10),
            "challenger_prediction_confidence": round(
                prediction_confidence(challenger_score, challenger_prediction), 10
            ),
            "nearest_neighbor_record_id": neighbor["record_id"],
            "nearest_neighbor_source_dataset": neighbor["source_dataset"],
            "nearest_neighbor_source_label": int(neighbor["label"]),
            "nearest_neighbor_similarity": round(float(neighbor_similarity[index]), 8),
            "nearest_neighbor_same_source": neighbor["source_dataset"]
            == row["source_dataset"],
            "nearest_neighbor_same_label": neighbor["label"] == row["label"],
            "redacted_text_excerpt": redact_excerpt(
                row["text_content"],
                limit=int(protocol["review_queue"]["excerpt_character_limit"]),
            ),
        })

    overall = rate_summary(diagnostic_rows)
    by_source = grouped_rate_summary(diagnostic_rows, "source_dataset")
    by_label = grouped_rate_summary(diagnostic_rows, "source_label")
    by_fold = grouped_rate_summary(diagnostic_rows, "development_fold")
    by_truncation = grouped_rate_summary(diagnostic_rows, "truncated_at_512")
    by_length = grouped_rate_summary(diagnostic_rows, "pre_truncation_token_bucket")
    source_label_records = [
        {**record, "source_label_key": f"{record['source_dataset']}|label={record['source_label']}"}
        for record in diagnostic_rows
    ]
    by_source_label = grouped_rate_summary(source_label_records, "source_label_key")
    source_truncation_records = [
        {
            **record,
            "source_truncation_key": (
                f"{record['source_dataset']}|truncated_at_512="
                f"{str(record['truncated_at_512']).lower()}"
            ),
        }
        for record in diagnostic_rows
    ]
    by_source_truncation = grouped_rate_summary(
        source_truncation_records, "source_truncation_key"
    )

    truncated = by_truncation.get("True", rate_summary([]))
    not_truncated = by_truncation.get("False", rate_summary([]))
    truncation_differences = {}
    for key in (
        "baseline_error_rate",
        "challenger_error_rate",
        "e5_regression_rate",
        "e5_recovery_rate",
        "net_e5_regression_rate",
    ):
        left = truncated[key]
        right = not_truncated[key]
        truncation_differences[f"truncated_minus_not_truncated_{key}"] = (
            None if left is None or right is None else round(left - right, 6)
        )

    neighbor_by_transition = {
        name: neighbor_summary(
            record for record in diagnostic_rows if record["transition"] == name
        )
        for name in ("both_correct", "e5_regression", "e5_recovery", "both_wrong")
    }
    neighbor_report = {
        "all": neighbor_summary(diagnostic_rows),
        "by_transition": neighbor_by_transition,
    }
    queue, queue_strata = review_queue(diagnostic_rows, protocol)
    write_jsonl(paths["row_diagnostics"], (
        {key: value for key, value in record.items() if key != "redacted_text_excerpt"}
        for record in diagnostic_rows
    ))
    write_jsonl(paths["review_queue"], queue)

    # Highest positive net regression is the largest deterioration.
    top_source_decline = max(
        by_source,
        key=lambda source: (
            by_source[source]["net_e5_regression_rate"], source
        ),
    )
    report = {
        "analysis_id": ANALYSIS_ID,
        "run_at": args.run_at,
        "status": "FROZEN_TRAIN_OOF_DIAGNOSTIC_COMPLETE_NO_TUNING",
        "protocol": {
            "path": str(args.protocol),
            "sha256": sha256_file(args.protocol),
        },
        "inputs": {
            "split": {"path": str(args.input), "sha256": sha256_file(args.input)},
            "predictions": {
                "path": str(args.predictions),
                "sha256": sha256_file(args.predictions),
            },
            "embeddings": {
                "path": str(args.embeddings),
                "sha256": sha256_file(args.embeddings),
            },
            "embedding_metadata": {
                "path": str(args.embedding_metadata),
                "sha256": sha256_file(args.embedding_metadata),
            },
            "development_result": {
                "path": str(args.development_result),
                "sha256": sha256_file(args.development_result),
            },
        },
        "scope": {
            "partition": "train",
            "row_count": len(diagnostic_rows),
            "group_count": len({record["split_group_id"] for record in diagnostic_rows}),
            "data_access": access,
        },
        "transition_summary": overall,
        "by_source_dataset": by_source,
        "by_source_label": by_source_label,
        "by_source_label_value": by_label,
        "by_development_fold": by_fold,
        "truncation_diagnostic": {
            "by_truncated_at_512": by_truncation,
            "by_source_and_truncated_at_512": by_source_truncation,
            "truncated_minus_not_truncated": truncation_differences,
            "by_pre_truncation_token_bucket": by_length,
            "interpretation": protocol["truncation_diagnostic"]["interpretation"],
        },
        "nearest_neighbor_diagnostic": {
            **neighbor_report,
            "candidate_exclusions": protocol["nearest_neighbor_diagnostic"][
                "candidate_exclusions"
            ],
            "interpretation": protocol["nearest_neighbor_diagnostic"]["interpretation"],
        },
        "descriptive_findings": {
            "largest_net_regression_source": top_source_decline,
            "largest_net_regression_rate": by_source[top_source_decline][
                "net_e5_regression_rate"
            ],
            "truncated_rows": truncated["row_count"],
            "truncated_challenger_error_rate": truncated["challenger_error_rate"],
            "not_truncated_challenger_error_rate": not_truncated[
                "challenger_error_rate"
            ],
            "truncated_regression_rate": truncated["e5_regression_rate"],
            "not_truncated_regression_rate": not_truncated["e5_regression_rate"],
            "all_nearest_neighbor_same_source_rate": neighbor_report["all"][
                "same_source_rate"
            ],
            "all_nearest_neighbor_same_label_rate": neighbor_report["all"][
                "same_label_rate"
            ],
            "regression_nearest_neighbor_same_source_rate": neighbor_by_transition[
                "e5_regression"
            ]["same_source_rate"],
            "regression_nearest_neighbor_same_label_rate": neighbor_by_transition[
                "e5_regression"
            ]["same_label_rate"],
        },
        "review_queue": {
            "row_count": len(queue),
            "unique_group_count": len({record["split_group_id"] for record in queue}),
            "strata_counts": queue_strata,
            "policy": protocol["review_queue"],
            "human_relabeling_performed": False,
            "training_eligibility_changed": False,
        },
        "quality_gates": {
            "protocol_hash_verified": True,
            "all_pinned_input_hashes_verified": True,
            "train_rows_exact": len(diagnostic_rows) == 3916,
            "train_groups_exact": len({record["split_group_id"] for record in diagnostic_rows})
            == 3783,
            "predictions_cover_train_exactly": set(prediction_by_id) == set(row_by_id),
            "embedding_rows_align_exactly": np.array_equal(embedding_ids, expected_ids),
            "transition_counts_sum_to_rows": sum(
                overall["transition_counts"].values()
            )
            == 3916,
            "nearest_neighbor_excludes_same_group": all(
                record["split_group_id"]
                != row_by_id[record["nearest_neighbor_record_id"]]["split_group_id"]
                for record in diagnostic_rows
            ),
            "review_queue_within_limit": all(value <= 5 for value in queue_strata.values()),
            "review_queue_groups_unique_within_stratum": True,
            "validation_text_rows_retained_zero": access["validation_text_rows_retained"] == 0,
            "validation_labels_accessed_zero": access["validation_labels_accessed"] == 0,
            "test_text_rows_retained_zero": access["test_text_rows_retained"] == 0,
            "test_labels_accessed_zero": access["test_labels_accessed"] == 0,
        },
        "safety_contract": {
            "new_embedding_operations": 0,
            "encoder_forward_passes": 0,
            "model_fit_operations": 0,
            "model_scoring_operations": 0,
            "validation_rows_used": 0,
            "test_rows_used": 0,
            "external_rows_used": 0,
            "labels_changed": 0,
            "training_eligibility_changes": 0,
            "model_selection_changes": 0,
            "deployment_allowed": False,
        },
        "artifacts": {},
        "interpretation_limits": [
            "All findings are descriptive associations on already-opened train OOF artifacts.",
            "Truncation is confounded with source and document type and is not a causal explanation.",
            "Nearest-neighbor source alignment is evidence of representation geometry, not a per-record causal attribution.",
            "This analysis cannot authorize a new encoder, chunking rule, classifier setting or threshold.",
        ],
    }
    failed_quality = [
        name for name, passed in report["quality_gates"].items() if not passed
    ]
    if failed_quality:
        raise ValueError("Error-analysis quality gates failed: " + ", ".join(failed_quality))
    report["artifacts"] = {
        "row_diagnostics": {
            "path": str(paths["row_diagnostics"]),
            "sha256": sha256_file(paths["row_diagnostics"]),
            "record_count": len(diagnostic_rows),
        },
        "review_queue": {
            "path": str(paths["review_queue"]),
            "sha256": sha256_file(paths["review_queue"]),
            "record_count": len(queue),
        },
    }
    paths["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "report": str(paths["report"]),
        "report_sha256": sha256_file(paths["report"]),
        "row_diagnostics_sha256": report["artifacts"]["row_diagnostics"]["sha256"],
        "review_queue_sha256": report["artifacts"]["review_queue"]["sha256"],
        "transition_summary": overall,
        "descriptive_findings": report["descriptive_findings"],
        "validation_opened": False,
        "model_fit_operations": 0,
        "new_embedding_operations": 0,
    }, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
