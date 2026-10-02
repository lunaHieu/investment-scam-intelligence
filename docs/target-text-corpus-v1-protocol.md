# Target Text Corpus V1 protocol

Status: **frozen before new target-data acquisition** on 2026-10-02.

This protocol defines the target task and the minimum evidence, review, grouping, and data gates for a future investment-solicitation text corpus. It does not authorize data acquisition, labeling, model fitting, scoring, or opening any validation/test partition.

## Target task

The prediction unit is an observed `POST`, `MESSAGE`, or `WEBSITE_SNAPSHOT` artifact linked to case-level ground truth.

- Positive (`1`): a `CONFIRMED` case with reviewed evidence linking the exact entity, domain, or artifact to an unauthorized, deceptive, impersonating, or fraudulent solicitation or operation.
- Negative (`0`): a `LEGITIMATE` case whose official identity, domain, and content context agree, with no unresolved evidence of cloning, compromise, redirect, or impersonation.
- `UNCERTAIN`: retained with provenance but excluded from binary fitting, model selection, thresholding, and headline evaluation.

The target is a research risk score. It is not a legal finding, investment recommendation, or universal scam probability. Warning documents, complaints, review rationale, source identifiers, evidence types, label confidence, and verification status cannot be predictive inputs.

## Evidence and review gates

Every eligible artifact must preserve an immutable raw capture, capture and exact-text SHA-256 hashes, source URL, collection time, language, and case/campaign, entity/domain-family, and near-duplicate group identifiers. Binary-eligible records require `HIGH` confidence and `RECONCILED` review status.

Every binary-eligible record receives:

1. a primary review;
2. an independent second review without the first reviewer's rationale;
3. reconciliation or routing to `UNCERTAIN` when reviewers disagree; and
4. project-owner acceptance before eligibility.

AI may assist with provenance extraction, hashing, structural validation, bounded evidence summaries, independent review recommendations, duplicate detection, and contradiction screening. It cannot silently create final labels, override conflicting evidence, infer legitimacy from the absence of a warning, or use model predictions as evidence.

## Source roles and leakage controls

The Mendeley V2 data remains a historical heterogeneous benchmark and contributes zero rows to the new target corpus. Every already-opened external cohort remains diagnostic-only and contributes zero rows to training or model selection.

The exclusion index must block exact capture, exact text, case/campaign, entity/domain-family, and normalized near-duplicate overlap with opened cohorts and across partitions. Probable cross-domain clones require manual review. Official warning and registry sources can support evidence or candidate discovery, but their warning or registry text cannot become the artifact being predicted.

## Minimum data gates

| Gate | CONFIRMED groups | LEGITIMATE groups | Training allowed |
|---|---:|---:|---|
| Schema and review pilot | 20 | 20 | No |
| Development corpus | 120 | 120 | Only after every gate passes |
| Untouched external holdout | 30 | 30 | Never used for fitting or selection |

The development corpus must use at least two acquisition channels per label, with no channel contributing more than 50% of either label. Independent second-review and reconciled high-confidence coverage must both equal 100%.

Development groups are partitioned 70/15/15 into train, validation, and internal test using the transitive union of case/campaign, entity/domain-family, and near-duplicate groups. At minimum, each label must contribute 84 train groups, 18 validation groups, and 18 internal-test groups. The split seed, algorithm, and artifact hashes must be frozen.

The untouched external holdout must contain at least 30 groups per label, come from a separate acquisition wave, and be frozen before the first model candidate is selected.

## Model-opening sequence

1. Run grouped out-of-fold development on target-corpus `train` only.
2. Open validation only when every predeclared development gate passes.
3. Open internal test once for one frozen candidate that passes one validation confirmation without retuning.
4. Open the untouched external holdout only after the final internal candidate and threshold are frozen.

Already-opened external cohorts and Mendeley validation/test partitions cannot be reused to select a model for the new target task.

## Current gate

At freeze time, zero new target records have been acquired, zero labels have been created or changed, and zero model fitting, scoring, or validation/test-opening operations have occurred. Training and deployment remain blocked.

The next permitted step is limited to two provenance-only artifacts: a candidate-source inventory and an exclusion index for every opened external cohort. Capture and labeling remain blocked until both artifacts verify.

