"""Small dependency-free guards for ISI V1 data contracts."""

from __future__ import annotations

FORBIDDEN_PREDICTIVE_FEATURES = frozenset({
    "source_id", "evidence_type", "ground_truth_status", "label_confidence",
    "review_notes", "verification_status", "warning_document",
})


def assert_feature_columns(columns: set[str] | list[str] | tuple[str, ...]) -> None:
    """Reject metadata that would leak review/source information into a model."""
    violations = sorted(set(columns) & FORBIDDEN_PREDICTIVE_FEATURES)
    if violations:
        raise ValueError(f"Leakage-prone predictive features are forbidden: {', '.join(violations)}")


def assert_gold_is_untouched(split_name: str, operation: str) -> None:
    """Make Gold evaluation explicitly evaluation-only in future pipeline adapters."""
    if split_name.lower() == "gold" and operation.lower() in {"fit", "tune", "select_threshold", "select_model"}:
        raise ValueError("Gold split is evaluation-only and cannot be used for fitting or selection.")
