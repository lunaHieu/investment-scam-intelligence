# SEC EDGAR/IAPD Wayback Availability Retry V10

Date: 2026-10-21
Status: frozen offline; two-row supplemental retry waiting 24-hour cooldown

V10 is bound to the immutable V9 report created at
`2026-10-21T18:18:58.983066+07:00` and its independent partial-pass QA. It
preserves all 113 resolved V9 rows and may retry only these two rows, in this
exact order:

1. `TTCV1_EDGAR_AVAIL_HOLDOUT_011`
2. `TTCV1_EDGAR_AVAIL_HOLDOUT_018`

The retry population contains zero `DEVELOPMENT` and two `EXTERNAL_HOLDOUT`
rows. The release cannot execute before
`2026-10-22T18:18:58.983066+07:00`, exactly 86,400 seconds after V9.

The authoritative V10 executor creates an exclusive `.partial` reservation
before networking, checkpoints after each logical attempt, never resumes a
partial, never overwrites an output, permits one logical attempt per row, uses
at least 60 seconds between attempts, and stops immediately on HTTP 429.

The separately frozen 58-row V5 capture release remains byte-for-byte
unchanged. V10 does not block, enlarge or mutate that plan. Capture was deferred
only because V9 encountered HTTP 429 in the same run. At the next scheduled
run, V10 is attempted first; capture V5 may follow only if V10 does not encounter
another HTTP 429.

Any row resolved by V10 remains supplemental and requires a separate future
plan amendment. Candidate live-domain access, automatic labeling,
validation/test access, model scoring and training remain prohibited.
