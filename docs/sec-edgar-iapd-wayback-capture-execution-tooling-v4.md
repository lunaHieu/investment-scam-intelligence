# SEC EDGAR/IAPD Wayback capture execution tooling V4

## Step name

Predeclare the V7-derived, hash-bound, 24-hour-cooled archive capture release.

## Meaning

The V4 release builder accepts only capture-plan tooling V4 and its exact
independent QA. It verifies the V7 plan generation, all-115-row recomputation,
all-and-only-available order and every plan/QA/final-result hash binding.

The release `not_before` must be at least 86,400 seconds after the final V7
availability report `created_at`; the boundary passes and one second earlier
fails. Release creation also cannot be later than `not_before`.

The frozen archive rules remain unchanged: only raw Wayback replay, at least 30
seconds between requests, one attempt per snapshot, immediate stop on HTTP
429, no live candidate-domain access, no replacement of failed rows and no
overwrite of existing outputs. The V1 execution/report identities are retained
for frozen executor and raw-byte verifier compatibility, while
`tooling_version=v4` and the V4 QA identity preserve the stronger lineage.

## Current gate

This is offline release tooling only. It authorizes no immediate network
execution and creates no raw HTML. A concrete release can be prepared only
after a real V4 plan passes independent QA, and execution must wait until its
verified `not_before`. Extraction, labeling, validation/test and training
remain closed.
