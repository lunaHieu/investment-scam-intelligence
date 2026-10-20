# SEC EDGAR/IAPD Wayback Availability Retry V9

Date: 2026-10-20  
Status: frozen offline; capture blocked; no network execution performed

V9 is bound to the immutable V8 report created at
`2026-10-20T14:19:54.213531+07:00` and its independent partial-pass QA. It
preserves all 113 resolved V8 rows and may retry only these two rows, in this
exact order:

1. `TTCV1_EDGAR_AVAIL_HOLDOUT_011`
2. `TTCV1_EDGAR_AVAIL_HOLDOUT_018`

The population is zero `DEVELOPMENT` and two `EXTERNAL_HOLDOUT` rows. The
release cannot execute before `2026-10-21T14:19:54.213531+07:00`, exactly
86,400 seconds after V8.

Immutable independent release QA passed offline and is stored as
`independent_retry_release_qa_v9.json` with SHA-256
`6746b158c9c98c3db9253b2af04acb764e38779e644b351d3f0fb19c70552c6c`.
It pins all 115 plan rows, all 113 preserved results, the exact ordered two-row
retry set, the 0/2 cohort composition, the cooldown, pacing, request bounds,
output identity, and every closed safety gate. QA performed zero network
operations.

The authoritative V9 executor creates an exclusive `.partial` reservation
before networking, checkpoints atomically after each logical attempt, refuses
to resume a partial, refuses overwrite, permits one logical attempt per row,
uses at least 60 seconds between requests, and stops immediately on HTTP 429.
It records logical attempts separately from HTTP requests so bounded redirects
cannot corrupt accounting.

Candidate live-domain access, archived-page download, capture, labeling,
validation/test access, model scoring, and training remain prohibited.

Capture Tooling V4 supports only a complete availability V7 result.
Therefore even `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` from V9 is only a
signal that separate V9-aware capture tooling may be prepared; it is not
authorization to use V4 or to capture any content.
