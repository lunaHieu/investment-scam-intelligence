# Reproducibility current state V31

V31 replaces the project-wide interpretation of the V11 recovery gate with a
non-blocking archive-acquisition lane and an authoritative V2 executor.

## What changed

- The immutable V1 recovery release and its `not_before` are unchanged.
- `scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2` is authoritative;
  the historical V1 executor is forbidden for the pending execution.
- Finalization is atomic. A completed network result cannot leave a final
  report plus a stale reservation and falsely trigger another acquisition.
- A complete crash-interrupted partial can be independently checked and
  promoted offline with zero requests.
- Archive failures are classified. Only HTTP 429 uses `Retry-After` or bounded
  exponential rate-limit backoff. Transport errors use shorter bounded delays;
  deterministic parser/content failures forbid an identical retry.
- A maximum of three network attempts applies per artifact family, after which
  the artifact is quarantined rather than generating an unlimited release
  chain.
- Supplemental and external-holdout acquisition is explicitly non-blocking.

## Current V11 state

The two recovery rows remain supplemental `EXTERNAL_HOLDOUT` records. No new
network request has been made. Their frozen execution time remains
`2026-10-27T08:42:13.975064+07:00`, but this is only the recovery lane's gate,
not the next gate for the entire project.

At that time the executor must be invoked with
`configs/sec_edgar_iapd_v11_metadata_recovery_execution_amendment_v2.json`.
Any failure must be evaluated by `scripts.archive_retry_policy_v1`; another
automatic fixed-24-hour release is forbidden.

## Unchanged boundaries

No candidate live domain may be accessed. The frozen 58-row capture, 56-row
review population, and owner acceptance remain immutable. The two supplemental
rows cannot silently enter training or the accepted external benchmark.
Validation/test opening, model scoring, and training remain unchanged by this
operational policy.
