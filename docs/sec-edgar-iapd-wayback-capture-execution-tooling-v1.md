# SEC EDGAR/IAPD Wayback capture execution tooling V1

## Step name

Predeclare hash-bound archive capture and byte-level result verification.

## Meaning

This tooling adds a second gate after snapshot-plan QA. The release builder pins
the capture plan and its independent QA, an explicit timezone-aware
`not_before`, and an immutable report target. Its execution contract permits
only `https://web.archive.org` raw replay URLs, one attempt per snapshot, at
least 30 seconds between requests, at most three archive-internal redirects,
HTML responses no larger than 25 MiB, and an immediate stop after HTTP 429.

The executor reproduces release verification immediately before network use,
refuses existing reports or raw targets, never accesses a candidate live
domain, writes each payload with exclusive creation, preserves every failure,
and never replaces a failed row. Tests replace networking with deterministic
fixtures and cover both successful cohort-preserving capture and the
`not_before` refusal.

The result verifier is independent of the executor. It joins the report back to
the frozen plan in original order and recomputes every captured file size and
SHA-256. Missing or modified bytes, unexpected files for failures, changed
metadata, incorrect aggregates, or a mismatched 429 stop fail QA. A partial
capture can pass integrity QA but receives
`PASS_PARTIAL_CAPTURE_RETRY_REQUIRED_TEXT_EXTRACTION_BLOCKED`; only a complete
capture can release preparation of text extraction.

## Current gate

The tooling is frozen before the real capture plan exists. No release, raw HTML
or result has been created, and no network request was made. After V3 completes,
the actual plan and plan QA must be materialized first. A concrete execution
release and its independent QA must then be created and hash-registered before
the executor may run. Labels, model operations, validation/test access and
training remain prohibited.
