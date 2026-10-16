# SEC EDGAR/IAPD Wayback capture-plan tooling V2

## Step name

Generalize exact snapshot-plan construction across availability V3, V4 and V5.

## Meaning

V1 froze the correct all-and-only-available selection rule but named and
validated only V3 evidence. The active availability chain has since advanced to
V5. V2 removes that version lock without weakening the gate: it recognizes only
the explicitly supported V3, V4 and V5 report identities and requires the
matching independent-QA hash field (`v3_sha256`, `v4_sha256` or `v5_sha256`).

The builder still requires exactly 115 rows, `status=COMPLETE`, zero unresolved
errors, `capture_plan_construction_ready=true`, QA status
`PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED`, an exact release hash, and an exact
result hash in the generation-specific QA field. The release ID and its planned
report ID must also match that same V3, V4 or V5 generation. It then includes every and only
row with `available=true`, in original order, preserving `DEVELOPMENT` and
`EXTERNAL_HOLDOUT` identities. Partial V5, a cross-generation QA binding, or a
changed release/result hash fails closed.

The independent verifier reloads the release, availability result and QA,
verifies every hash and generation binding, reconstructs all membership and
order, checks raw Wayback replay URLs, path containment, cohort counts and the
unavailable aggregate. Synthetic tests exercise complete V3, V4 and V5 inputs
and explicitly prove that partial V5 and wrong-generation evidence remain
blocked.

For compatibility with the already frozen capture-execution V1 contract, the
plan report ID and historical status token remain unchanged. New generic fields
`availability_result`, `independent_availability_qa` and
`availability_generation` carry the actual evidence generation and final
availability `created_at`; no V5 artifact
is mislabeled in a version-specific field.

## Current gate

This change is offline tooling readiness only. It creates no real plan, performs
no network request or capture, and does not open label, validation/test, model or
training access. A real plan may be materialized only after a supported
availability result and its independent QA pass the complete-result gate.
