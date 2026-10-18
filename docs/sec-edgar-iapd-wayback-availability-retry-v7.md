# SEC EDGAR/IAPD Wayback Availability Retry V7

Date: 2026-10-18  
Status: frozen offline; capture blocked; no network execution performed

V7 is bound to the immutable V6 report created at
`2026-10-18T09:45:26.642053+07:00` and its independent partial-pass QA. It
preserves all 107 resolved V6 rows and may retry only these eight rows, in this
exact order:

1. `TTCV1_EDGAR_AVAIL_DEV_064`
2. `TTCV1_EDGAR_AVAIL_DEV_070`
3. `TTCV1_EDGAR_AVAIL_DEV_074`
4. `TTCV1_EDGAR_AVAIL_DEV_082`
5. `TTCV1_EDGAR_AVAIL_HOLDOUT_001`
6. `TTCV1_EDGAR_AVAIL_HOLDOUT_009`
7. `TTCV1_EDGAR_AVAIL_HOLDOUT_011`
8. `TTCV1_EDGAR_AVAIL_HOLDOUT_018`

The population is four `DEVELOPMENT` and four `EXTERNAL_HOLDOUT` rows. The
release cannot execute before `2026-10-19T09:45:26.642053+07:00`, exactly
86,400 seconds after V6.

Immutable independent release QA passed offline and is stored as
`independent_retry_release_qa_v7.json` with SHA-256
`901d777a5a845e7b2799b32520a1613be318f8818f16d321df98b83eb8d0adf4`.
It pins all 115 plan rows, all 107 preserved results, the exact ordered eight-row
retry set, the 4/4 cohort composition, the cooldown, pacing, request bounds,
output identity, and every closed safety gate. QA performed zero network
operations.

The authoritative V7 executor creates an exclusive `.partial` reservation
before networking, checkpoints atomically after each logical attempt, refuses
to resume a partial, refuses overwrite, permits one logical attempt per row,
uses at least 60 seconds between requests, and stops immediately on HTTP 429.
It records logical attempts separately from HTTP requests so bounded redirects
cannot corrupt accounting.

Candidate live-domain access, archived-page download, capture, labeling,
validation/test access, model scoring, and training remain prohibited.

Capture Tooling V3 supports only availability generations V3 through V6.
Therefore even `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` from V7 is only a
signal that separate V7-aware capture tooling may be prepared; it is not
authorization to use V3 or to capture any content.
