# SEC EDGAR/IAPD Wayback capture-plan tooling V4

## Step name

Predeclare exact V7-only capture-plan construction with full 115-row recomputation.

## Meaning

V4 accepts only the V7 availability release, V7 final report and V7 independent
QA as one hash-bound generation tuple. It never falls back to or mutates V3
tooling. Prior-generation result-hash fields in the V7 QA are rejected.

The builder and independent verifier both reload the immutable 115-row source
plan. They compare every result in original order, recompute availability/error
states and aggregates, and require the QA status
`PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED`. Any unresolved row, incomplete
status, failed QA or mismatched hash keeps capture planning closed.

After those checks, every and only `available=true` row is selected in source
order. `DEVELOPMENT` and `EXTERNAL_HOLDOUT` identities are preserved, raw
Wayback `id_` replay URLs are generated, target paths are confined below the
raw root, and existing immutable targets are rejected.

## Current gate

This tooling registration is offline preparation only. It performs no network
operation and creates no capture artifact. A real plan may be materialized only
after a complete V7 result and its exact independent QA pass all checks.
Capture, extraction, labeling, validation/test and training remain closed.
