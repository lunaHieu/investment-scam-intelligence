# Archive acquisition control policy V1

Date: 2026-10-26  
Status: active for new archive operations; historical releases remain immutable

## Problem addressed

The former workflow converted nearly every acquisition failure into another
fixed 24-hour gate. That rule was conservative but incorrect as a general
failure policy: a parser defect, DNS error, local finalization crash, empty CDX
result, and HTTP 429 do not have the same cause or remedy. Repeating an
identical request after 24 hours also created an unbounded loop.

Internet Archive's automation guidance requires a descriptive User-Agent,
delays for bulk work, honoring HTTP 429 and `Retry-After`, caching to avoid
repeat downloads, graceful error handling, and exponential backoff. It does
not prescribe a universal 24-hour delay for every error.

## Binding control rules

1. Archive acquisition is a **non-blocking lane**. A quarantined supplemental
   or external-holdout artifact cannot stop independent data, review,
   documentation, evaluation-preparation, or engineering work.
2. Each artifact has at most three network attempts in one acquisition family.
   Exhaustion means quarantine, not an unbounded new release chain.
3. HTTP 429 honors a valid `Retry-After`. Without one, bounded exponential
   delays are 15 minutes, 1 hour, 6 hours, then 24 hours; the 24-hour value is a
   cap, not the default for every failure.
4. DNS, timeout, and HTTP 5xx use bounded 5-minute, 15-minute, and 1-hour
   delays. They do not inherit a 24-hour rate-limit gate.
5. HTTP 4xx other than 429, invalid content, empty results, and known parser
   limitations forbid an identical blind retry. They require a changed query,
   alternate evidence, or quarantine.
6. A local finalization error with persisted raw bytes and response metadata is
   repaired offline immediately. It must never cause another download.
7. Persisted bytes with missing response metadata remain supplemental evidence.
   Recapture is optional only for a genuinely required artifact and cannot
   block the rest of the project.
8. Every executor reserves before network, stops on 429, preserves diagnostic
   headers, writes no live-domain request, and never overwrites an artifact.

## Crash-safe finalization

The V2 finalizer replaces the reservation atomically with a complete report at
the partial path, verifies it, and then atomically promotes it to the final
path. The only recoverable crash states are therefore:

- a reservation: preserve it and investigate; or
- a complete independently verifiable partial: promote it offline with zero
  network operations.

A successful final report plus a stale reservation is no longer a valid end
state.

## Current V11 decision

The two V11 rows are supplemental `EXTERNAL_HOLDOUT` artifacts. Their existing
V1 `not_before` remains unchanged because the historical release is immutable,
but this gate is no longer the project-wide next gate. Execution must use the
V2 amendment and executor. If it encounters an error, the policy evaluator
chooses offline reconciliation, bounded retry, changed evidence, or quarantine;
no automatic new 24-hour release is allowed.

Official references:

- https://archive.org/developers/bots.html
- https://archive.org/developers/tutorial-get-snapshot-wayback.html
