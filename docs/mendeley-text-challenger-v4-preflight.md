# Mendeley Text Challenger V4 — frozen semantic preflight

## Outcome

The first semantic challenger is now fully specified but has not been run. The only candidate is a frozen `intfloat/e5-small-v2` encoder followed by the same fixed logistic-regression classifier and 0.5 threshold used by Text Baseline V2.

This stage performed acquisition, dependency/license audit, checksum verification and an offline load test only. It performed zero forward passes, zero embedding operations, zero classifier fits and zero scoring operations.

## Why this encoder was selected

Three small English sentence encoders were screened without using internal-test or external-benchmark performance:

| Candidate | License | Width | Context | Decision |
|---|---|---:|---:|---|
| `sentence-transformers/all-MiniLM-L6-v2` | Apache-2.0 | 384 | 256 | Not selected because its shorter context would discard more long-form input |
| `BAAI/bge-small-en-v1.5` | MIT | 384 | viable | Viable reserve, but not compared experimentally |
| `intfloat/e5-small-v2` | MIT | 384 | 512 | Selected because its official card gives an explicit linear-probing feature contract |

The selected immutable revision is `ffb93f3bd4047442299a41ebb6fa998a38507c52`. Its 133,466,304-byte Safetensors file has SHA-256 `45bfa60070649aae2244fbc9d508537779b93b6f353c17b0f95ceccb1c5116c1`.

## Frozen representation

Each `text_content` value will be prefixed with `query: `, tokenized locally with a 512-token maximum and right truncation, encoded in evaluation/inference mode, pooled by attention-mask-aware mean pooling, then row-normalized to L2 norm 1. No external lowercase or text cleanup is added.

The encoder remains frozen. There is one candidate, one classifier configuration and one threshold. No encoder comparison, fine-tuning, C search or threshold search is allowed.

## Data boundary

Development may access only the 3,916 `train` rows from `group_split_v2`. It uses deterministic four-fold grouped OOF comparison against a freshly fit word TF-IDF baseline on the exact same folds. Auxiliary, quarantine, validation, internal test and every opened external benchmark remain inaccessible during development.

Validation may be opened once only if every OOF development gate passes. Even if validation also passes, internal test remains closed and the result is only a research candidate. A new untouched, evidence-backed external cohort is still required before any headline generalization claim.

## Promotion logic

The primary measure remains the unweighted mean of per-source Macro-F1. Promotion requires all predeclared performance and robustness gates, including no increase in OOF source predictability and no material single-source regression. Failure of any development gate ends this branch before validation.

## Reproducibility and licensing

The model snapshot lives outside Git at:

`D:\nckh 2026-2027\ISI_Data\models\intfloat_e5-small-v2\ffb93f3bd4047442299a41ebb6fa998a38507c52`

The repository stores a per-file checksum manifest and the complete Python environment lock. The selected model is MIT licensed; direct loading dependencies are under MIT, BSD-3-Clause or Apache-2.0 licenses. Notices and attribution must be preserved if artifacts are redistributed.

The authoritative machine-readable contract is `configs/mendeley_text_challenger_v4_protocol.json`.
