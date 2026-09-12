"""Audit normalized text overlap across Mendeley train/validation/test splits.

The audit never changes the source CSV. It reports exact normalized duplicates
and template-level duplicate candidates (URLs, emails, handles and numbers
masked). Template candidates are diagnostic signals, not definitive duplicates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+|\[URL\]", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b|\[EMAIL\]", re.IGNORECASE)
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]+|\[HANDLE\]", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")


def normalize_surface(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(TOKEN_RE.findall(text))


def normalize_template(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = URL_RE.sub(" tokenurl ", text)
    text = EMAIL_RE.sub(" tokenemail ", text)
    text = HANDLE_RE.sub(" tokenhandle ", text)
    text = NUMBER_RE.sub(" tokennumber ", text)
    return " ".join(TOKEN_RE.findall(text))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"record_id", "text_content", "label", "partition", "source_dataset"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(required)}")
        for row in reader:
            if row.get("partition") in {"train", "validation", "test"}:
                rows.append(row)
    return rows


def analyze_key(rows: list[dict[str, str]], key_name: str, key_fn, min_tokens: int) -> dict:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        key = key_fn(row.get("text_content") or "")
        if len(key.split()) >= min_tokens:
            groups[digest(key)].append(index)

    duplicate_groups = [indices for indices in groups.values() if len(indices) > 1]
    cross_split = [
        indices for indices in duplicate_groups
        if len({rows[index]["partition"] for index in indices}) > 1
    ]
    train_overlap = [
        indices for indices in cross_split
        if "train" in {rows[index]["partition"] for index in indices}
    ]
    overlapping_eval_indices = {
        index
        for indices in train_overlap
        for index in indices
        if rows[index]["partition"] in {"validation", "test"}
    }
    conflicting_labels = [
        indices for indices in duplicate_groups
        if len({rows[index]["label"] for index in indices}) > 1
    ]

    examples = []
    for indices in train_overlap[:20]:
        examples.append({
            "partitions": sorted({rows[index]["partition"] for index in indices}),
            "labels": sorted({rows[index]["label"] for index in indices}),
            "source_datasets": sorted({rows[index]["source_dataset"] for index in indices}),
            "record_ids": [rows[index]["record_id"] for index in indices[:12]],
            "text_preview": (rows[indices[0]].get("text_content") or "")[:240],
        })

    eval_overlap_by_partition = Counter(rows[index]["partition"] for index in overlapping_eval_indices)
    eval_overlap_by_source = Counter(rows[index]["source_dataset"] for index in overlapping_eval_indices)
    return {
        "key": key_name,
        "minimum_tokens": min_tokens,
        "eligible_rows": sum(len(indices) for indices in groups.values()),
        "duplicate_groups_anywhere": len(duplicate_groups),
        "duplicate_rows_anywhere": sum(len(indices) for indices in duplicate_groups),
        "cross_split_groups": len(cross_split),
        "train_to_evaluation_groups": len(train_overlap),
        "evaluation_rows_overlapping_train": len(overlapping_eval_indices),
        "evaluation_overlap_by_partition": dict(sorted(eval_overlap_by_partition.items())),
        "evaluation_overlap_by_source_dataset": dict(sorted(eval_overlap_by_source.items())),
        "duplicate_groups_with_conflicting_labels": len(conflicting_labels),
        "examples": examples,
        "overlapping_eval_record_ids": sorted(rows[index]["record_id"] for index in overlapping_eval_indices),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, help="Optional baseline model JSON for clean-subset evaluation")
    args = parser.parse_args()
    rows = read_rows(args.input)
    partition_counts = Counter(row["partition"] for row in rows)
    blank_counts = Counter(
        row["partition"] for row in rows if not normalize_surface(row.get("text_content") or "")
    )
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(args.input),
        "scope": "Read-only text overlap audit; no source fields are model features.",
        "interpretation": {
            "surface_normalized": "Case, Unicode compatibility, punctuation and whitespace normalized.",
            "template_candidate": "Also masks URLs, emails, handles and numbers; candidate only, not definitive duplication.",
        },
        "row_count": len(rows),
        "partition_counts": dict(sorted(partition_counts.items())),
        "blank_text_by_partition": dict(sorted(blank_counts.items())),
        "surface_normalized": analyze_key(rows, "surface_normalized", normalize_surface, min_tokens=1),
        "template_candidate": analyze_key(rows, "template_candidate", normalize_template, min_tokens=10),
    }
    if args.model:
        from train_mendeley_text_baseline import evaluate

        model = json.loads(args.model.read_text(encoding="utf-8"))
        overlapping_ids = set(report["surface_normalized"]["overlapping_eval_record_ids"])
        report["clean_evaluation"] = {}
        for partition in ("validation", "test"):
            all_rows = [row for row in rows if row["partition"] == partition]
            clean_rows = [row for row in all_rows if row["record_id"] not in overlapping_ids]
            clean_sources = sorted({row["source_dataset"] for row in clean_rows})
            report["clean_evaluation"][partition] = {
                "removed_exact_overlap_rows": len(all_rows) - len(clean_rows),
                "remaining_rows": len(clean_rows),
                "metrics": evaluate(model, clean_rows) if clean_rows else None,
                "metrics_by_source_dataset": {
                    source: evaluate(
                        model,
                        [row for row in clean_rows if row["source_dataset"] == source],
                    )
                    for source in clean_sources
                },
            }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {
        "output": str(args.output),
        "row_count": report["row_count"],
        "partition_counts": report["partition_counts"],
        "blank_text_by_partition": report["blank_text_by_partition"],
        "surface_normalized": {
            key: report["surface_normalized"][key]
            for key in (
                "cross_split_groups", "train_to_evaluation_groups",
                "evaluation_rows_overlapping_train", "duplicate_groups_with_conflicting_labels",
            )
        },
        "template_candidate": {
            key: report["template_candidate"][key]
            for key in (
                "cross_split_groups", "train_to_evaluation_groups",
                "evaluation_rows_overlapping_train", "duplicate_groups_with_conflicting_labels",
            )
        },
    }
    if "clean_evaluation" in report:
        compact["clean_evaluation"] = {
            split: {
                "removed_exact_overlap_rows": values["removed_exact_overlap_rows"],
                "remaining_rows": values["remaining_rows"],
                "metrics": {
                    key: value
                    for key, value in (values["metrics"] or {}).items()
                    if key != "misclassified_examples"
                } if values["metrics"] else None,
            }
            for split, values in report["clean_evaluation"].items()
        }
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
