# SEC EDGAR/IAPD Wayback capture-plan tooling V3

## Step name

Predeclare exact V6-aware capture-plan construction with full population recomputation.

## Meaning

V3 adds the V6 availability report, retry release and independent QA as one
explicit generation tuple. V3, V4 and V5 remain supported only through their
own equally explicit tuples. A report, release, QA identity and
generation-specific result-hash field must all name the same generation;
cross-generation evidence fails closed.

The builder does not trust `status=COMPLETE` or reported aggregates alone. It
reloads the immutable 115-row availability source plan pinned by the retry
release, verifies its hash, and compares every result row in original order.
Identity fields, query timestamp, cohort, boolean availability, error state,
snapshot evidence and all aggregates are recomputed. Any unresolved row blocks
plan construction even when a synthetic or damaged report claims zero errors.

Only after that recomputation does the builder select every and only
`available=true` row in original order. It preserves `DEVELOPMENT` and
`EXTERNAL_HOLDOUT`, converts each Wayback URL to raw `id_` replay, confines all
targets below the declared raw root, and refuses existing targets. The
independent verifier reloads and hashes every release, source-plan, result and
QA input and reconstructs membership, order, cohort totals and replay URLs.

The historical capture-plan report identity and status token remain unchanged
for frozen executor compatibility. `tooling_version=v3` and V3 QA identity make
the stronger contract explicit.

## Current gate

This tooling freeze is offline only. It produces no real capture plan and makes
no network request. A real plan remains forbidden unless V6 (or an explicitly
supported prior complete generation) and its exact independent QA pass with all
115 rows resolved. Capture, labeling, validation/test and training remain
closed.
