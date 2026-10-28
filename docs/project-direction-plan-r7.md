# Project Direction Plan R7

Date: 2026-10-28

R7 records the independently verified exact-53 ready-channel capture execution
release.

## Current gate

- Exact population: 53 snapshots, 37 DEVELOPMENT and 16 EXTERNAL_HOLDOUT.
- Release QA: PASS; output and all capture targets are absent.
- Minimum pacing: 30 seconds; one attempt per snapshot.
- Crash-safe partial reservation, no overwrite, no automatic resume and stop on
  the first HTTP or transport error.
- No universal 24-hour cooldown was added. The release is eligible now, but
  execution must occur in a separate invocation.
- Current suite: 1025 tests passed; current registry target after navigation:
  273 analysis registries.

## Next order

1. Re-run release QA and execute the exact-53 capture once.
2. Independently verify every captured byte/hash. A partial result remains
   immutable and requires a separately declared missing-only release.
3. Only complete capture QA may open exact-text extraction and grouping.

Labels, validation/test, scoring and training remain closed.
