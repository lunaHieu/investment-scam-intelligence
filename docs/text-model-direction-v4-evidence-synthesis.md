# Text model direction V4 – evidence synthesis

## Decision

The current bottleneck is data and source robustness, not a lack of model capacity. Keep Text Baseline V2 frozen as the reference, do not deploy it, and do not move directly to an agentic or large generative model.

The next research hypothesis family is a frozen semantic sentence representation followed by a regularized linear classifier. This is a hypothesis only. No encoder, classifier configuration, or threshold has been selected, and no embeddings have been computed.

## Evidence across the two comparable external cohorts

| Cohort | Records | Macro-F1 | FP | FN |
|---|---:|---:|---:|---:|
| Wayback language V2 | 38 | 0.651868 | 9 | 4 |
| Untouched Wayback holdout V3 | 30 | 0.732143 | 5 | 3 |

A descriptive, non-preregistered aggregation gives 68 records, 21 errors, and Macro-F1 0.687869. This aggregate is context, not a new benchmark score.

Recurring failure evidence is stronger than the difference between the two point estimates:

- 14 false positives versus seven false negatives;
- 28/68 records lie within 0.10 of the frozen threshold;
- 50/68 nearest training references come from `spam_email`;
- 15/21 error cases have a nearest reference from `spam_email`;
- direct-address and generic marketing terms repeatedly push legitimate pages toward label 1;
- conventional trading and finance terms can push warned pages toward label 0.

## Retired directions

Character fragments are retired on the current validation partition because their small validation gain came with a 0.045508 increase in source predictability and an uncertainty interval crossing zero.

English stop-word removal is retired because validation Macro-F1 fell by 0.022497, worst-source Macro-F1 fell by 0.045249, and the paired interval was entirely below zero.

These failures do not prove that all lexical or stop-word methods are universally ineffective. They mean those already-opened choices must not be iterated against the same validation and external evidence.

## Why a frozen semantic representation is next

A sentence-level semantic representation is materially different from adding more word or character n-grams. Keeping the encoder frozen makes the first experiment auditable and limits capacity while testing whether semantic similarity reduces dependence on exact marketing and direct-address tokens.

The separate V4 development protocol must pin the exact encoder revision, license, file checksum, pooling, truncation, offline cache, classifier, and all promotion gates before any computation. Candidate development may use only eligible train data with grouped folds and one validation confirmation. The opened V1/V2/V3 external datasets may motivate the hypothesis but cannot select or tune it.

Any candidate that passes internal gates still requires a new untouched, evidence-backed external cohort. V2 and V3 cannot be reused as headline evaluation.
