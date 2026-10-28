# Project Direction Plan R6

Date: 2026-10-28

R6 records completion of the ready-channel CDX metadata stage and the offline
capture-plan gate.

## Verified state

- Canary row `002` and bulk rows `003`-`070` are complete and immutable.
- Bulk: 68/68 HTTP 200 JSON responses, zero 429 and zero transport errors.
- Eligible snapshots: 53 total after adding the canary; 37 DEVELOPMENT and 16
  EXTERNAL_HOLDOUT.
- Valid empty metadata: 16 rows, preserved without retry or substitution.
- Capture plan: exact 53, independently recomputed, raw replay only.
- Capture execution remains closed until a separate release is prepared and
  verified.
- Current lifecycle-aware suite target: 1021 tests; registry target after
  current navigation: 270 analyses.

## Next order

1. Build and independently verify a separate capture execution release for
   the exact 53-row plan, with pacing, no-overwrite and crash-safe partial
   output.
2. Execute capture only in a later invocation; independently verify every raw
   byte/hash.
3. After complete capture QA, run offline exact-text extraction and grouping.
4. Continue bounded primary review, blind second review and reconciliation.

Availability and archive membership are not labels. Validation/test, scoring
and training remain closed.
