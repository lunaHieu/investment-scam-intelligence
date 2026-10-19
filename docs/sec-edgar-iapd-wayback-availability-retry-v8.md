# SEC EDGAR/IAPD Wayback Availability Retry V8

Date: 2026-10-19  
Status: frozen offline; capture blocked; no network execution performed

V8 is bound to the immutable V7 report created at
`2026-10-19T14:06:35.423170+07:00` and its independent partial-pass QA. It
preserves all 113 resolved V7 rows and may retry only these two rows, in this
exact order:

1. `TTCV1_EDGAR_AVAIL_HOLDOUT_011`
2. `TTCV1_EDGAR_AVAIL_HOLDOUT_018`

The population is zero `DEVELOPMENT` and two `EXTERNAL_HOLDOUT` rows. The
release cannot execute before `2026-10-20T14:06:35.423170+07:00`, exactly
86,400 seconds after V7.

Immutable independent release QA passed offline and is stored as
`independent_retry_release_qa_v8.json` with SHA-256
`a0b329f726dd06ceab5eea1271c7825aa8b2220592d739756e9fbd2d5dd75c4f`.
It pins all 115 plan rows, all 113 preserved results, the exact ordered two-row
retry set, the 0/2 cohort composition, the cooldown, pacing, request bounds,
output identity, and every closed safety gate. QA performed zero network
operations.

The authoritative V8 executor creates an exclusive `.partial` reservation
before networking, checkpoints atomically after each logical attempt, refuses
to resume a partial, refuses overwrite, permits one logical attempt per row,
uses at least 60 seconds between requests, and stops immediately on HTTP 429.
It records logical attempts separately from HTTP requests so bounded redirects
cannot corrupt accounting.

Candidate live-domain access, archived-page download, capture, labeling,
validation/test access, model scoring, and training remain prohibited.

Capture Tooling V4 supports only a complete availability V7 result.
Therefore even `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` from V8 is only a
signal that separate V8-aware capture tooling may be prepared; it is not
authorization to use V4 or to capture any content.
