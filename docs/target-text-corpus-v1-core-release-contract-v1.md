# Dataset V1-Core balanced-release contract V1

## Step name

Predeclare independent validation of the balanced target-corpus release.

## Meaning

Owner acceptance is necessary but not sufficient for model use. A future
Dataset V1-Core proposal must contain exactly 240 fresh development groups and
60 untouched external-holdout groups. Each label has two fixed acquisition
channels: every channel contributes exactly 60 development groups and 15
external-holdout groups. Shortfalls cannot be borrowed between channels or
labels.

Every record must contain visible text from a raw Wayback replay, matching text
and raw-capture SHA-256 values, a timezone-aware collection time, reviewed
language, `HIGH` evidence confidence, primary and blind-review provenance,
reconciliation, owner acceptance, and a passing channel-contribution QA hash.
The record must also be fresh and pass opened-cohort and cross-partition
exclusions.

The validator rejects duplicate record IDs, exact texts, raw captures, replay
URLs, transitive groups, case/campaign groups, entity/domain-family groups, or
near-duplicate groups anywhere in the 300-group release. This makes the
development and holdout namespaces disjoint by construction rather than only
by their declared cohort field.

Per label, development must contain at least 12 reviewed non-English groups,
including at least 6 Vietnamese groups. External holdout must contain at least
3 reviewed non-English groups, including at least 2 Vietnamese groups.

## Closed model gates

Passing this validator does not assign `train`, `validation`, or
`internal_test`; those fields are forbidden in the proposed release. It only
permits preparation of a deterministic group-split plan. Training,
validation/internal-test opening, and external-holdout scoring remain closed.

## Current state

The contract and validator are tested using a synthetic 300-group manifest.
No real Dataset V1-Core manifest or channel contribution was created, and no
existing record became eligible for model use.
