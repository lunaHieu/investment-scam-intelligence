# SEC EDGAR/IAPD post-capture grouping tooling V1

## Step name

Predeclare opened-cohort exclusion and development/holdout disjoint grouping.

## Meaning

This offline gate compares every minimum-content text with the 107 previously
opened external records by exact raw hash, exact text hash, normalized host and
the frozen normalized five-word-shingle near-duplicate rule. It also constructs
deterministic transitive components among new records using exact host, exact
text and near-duplicate edges.

The cohort identity frozen before capture is preserved. If one technical group
contains both `DEVELOPMENT` and `EXTERNAL_HOLDOUT`, the holdout member is routed
out of the independent holdout rather than silently retained. The corresponding
development member remains review-only and the collision is reported. Group IDs
are exclusion-control identifiers only, not claims that records belong to one
real-world fraud or entity case.

An independent verifier rebuilds the complete analysis and requires canonical
equality. Even after a pass, primary label review remains closed until a bounded
manual group/clone review is prepared and completed.

## Current gate

The tooling is tested with deterministic synthetic text, including a deliberate
cross-cohort duplicate. No real grouping release or analysis exists because the
upstream V3, capture and exact-text stages have not completed. Network, labels,
model scoring, validation/test access and training remain closed.
