# Ready-channel Wayback availability execution amendment V2

Date: 2026-10-26

This amendment removes an obsolete coordination blocker from the immutable
exact-70 B5 availability release without changing its population, order,
cohorts, endpoint, pacing, output path, or safety controls.

## Root cause

The V1 coordination gate expected an A1 result with no `error` and referenced
an old QA filename. A1 actually received HTTP 200 `application/json` with the
canonical three-byte body `[]\n`. Its historical parser required a non-empty
CDX table and preserved a `ValueError`. Independent V2 QA proved this was a
terminal zero-row result, not a network failure or HTTP 429, and forbade an
identical retry.

Consequently, requiring A1 to be error-free would block an unrelated exact-70
availability plan forever even though the inherited cooldown ended on
2026-10-25.

## V2 execution rule

- Recompute the canonical-empty A1 QA from immutable report bytes and hashes.
- Require `network_failure=false`, `rate_limit=false`, and `retry_needed=false`.
- Preserve the original effective not-before and require it to have passed.
- Use the immutable V1 crash-safe `run_plan`, which reserves and checkpoints a
  partial journal before network and atomically promotes the final report.
- Keep one attempt per candidate, 60-second minimum pacing, stop on the first
  HTTP/transport error, preserve `Retry-After`, and never auto-resume.
- Execute only through the V2 wrapper and its independent amendment QA.

The action is archive-availability metadata only. It does not download archived
pages, contact candidate live domains, create labels, open model partitions, or
authorize training.
