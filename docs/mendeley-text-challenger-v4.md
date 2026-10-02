# Mendeley Text Challenger V4 — train-only semantic OOF result

## Decision

The exact frozen `intfloat/e5-small-v2` plus logistic-regression challenger is rejected at the development gate. Validation, internal test and all external benchmarks remain unopened for this challenger.

All six predeclared development gates failed. Text Baseline V2 remains the reference representation. No classifier or deployable model artifact was created.

## Scope actually used

- Partition embedded and evaluated: `train` only.
- Rows: 3,916.
- Complete `split_group_id` groups: 3,783.
- OOF design: four deterministic grouped folds with 989, 980, 979 and 968 evaluation rows.
- Validation text rows retained: zero.
- Validation labels accessed: zero.
- Internal-test rows retained: zero.
- Auxiliary and quarantine rows used: zero.
- External benchmark rows loaded: zero.

The frozen E5 encoder ran offline and was never fine-tuned. Embeddings were 384-dimensional float32 vectors using the pinned `query: ` prefix, 512-token right truncation, attention-mask-aware mean pooling and L2 normalization.

## Embedding audit

The train embedding matrix has shape 3,916 × 384. Every value is finite and every row passed the L2-norm tolerance.

There were 379 truncated rows (9.6782%): 364 `spam_email` rows, 15 `phishing` rows, and none from the two Twitter-derived sources. This is an important limitation of the frozen configuration, but it was not used to alter or rerun the experiment.

## OOF results

| Measure | Word TF-IDF baseline | Frozen E5 | Delta |
|---|---:|---:|---:|
| Pooled Macro-F1 | 0.721038 | 0.689907 | -0.031131 |
| Mean per-source Macro-F1 | 0.793988 | 0.747965 | -0.046023 |
| Worst-source Macro-F1 | 0.518193 | 0.500136 | -0.018057 |
| Source-predictability Macro-F1 | 0.916352 | 0.932908 | +0.016556 |
| Within-source shuffled-label Macro-F1 | 0.567752 | 0.586306 | +0.018554 |

Per-source Macro-F1 deltas were negative for every source:

| Source | Delta |
|---|---:|
| `cresci_stock_2018` | -0.027852 |
| `phishing` | -0.034955 |
| `spam_email` | -0.103227 |
| `twitter_bot_detection` | -0.018057 |

The maximum single-source decline was 0.103227 on `spam_email`, far above the allowed 0.01. E5 also increased rather than reduced source predictability.

## Gate outcome

The challenger failed all required conditions:

- insufficient mean per-source Macro-F1 delta;
- lower worst-source Macro-F1;
- excessive pooled Macro-F1 decline;
- excessive single-source decline;
- increased source predictability;
- excessive shuffled-label diagnostic delta.

Because development did not pass, the code did not create validation embeddings, did not fit on all train rows, and did not score validation. This is a protocol stop, not a discretionary choice after seeing validation.

## Interpretation limits

This result rejects only the exact frozen V4 configuration: E5-small-v2 at the pinned revision, 512-token right truncation, fixed mean pooling, fixed normalization and the inherited logistic-regression configuration. It does not prove that all semantic encoders, long-document strategies or hybrid lexical-semantic representations are ineffective.

The development results must not be used to start an unregistered search over encoders, pooling methods, chunking rules, classifier strengths or thresholds. Any new direction requires a separate hypothesis and protocol. The Mendeley label remains a harmonized source label rather than regulator-verified investment-scam ground truth.
