# Reproducibility Current State V5

Date: 2026-10-18  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v7.json`

This guide records the current safe path. It does not authorize live candidate
domain access, labeling from availability or registry membership, validation or
test opening, model training, or model scoring.

## Current SEC/IAPD state

- Availability plan: 115 rows in frozen order.
- V6 result: 107 resolved, 52 available, 55 unavailable, eight unresolved.
- V6 stopped after one request on HTTP 429; independent QA passed with errors
  preserved and capture blocked.
- V7 retries exactly the same ordered eight unresolved IDs: four DEVELOPMENT
  and four EXTERNAL_HOLDOUT.
- V7 `not_before`: `2026-10-19T09:45:26.642053+07:00`.
- Authoritative module: `scripts.retry_sec_edgar_iapd_wayback_availability_v7`.
- Final and partial V7 outputs are both terminal no-overwrite states.

Before execution, fetch `origin/main`, require a clean tree and local/remote
equality, verify the pinned preparation commit is an ancestor, run the V7
release verifier, `--verify-only`, focused tests, the full suite, and registry
validation. Execute only when neither `availability_report_v7.json` nor its
`.partial` journal exists. Never resume a partial journal.

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v7 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v7.json

.venv\Scripts\python.exe -m scripts.retry_sec_edgar_iapd_wayback_availability_v7 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v7.json `
  --verify-only
```

At or after the gate, remove `--verify-only` exactly once. The executor reserves
a journal before the first request, checkpoints every logical attempt, waits at
least 60 seconds between candidates, and stops immediately on HTTP 429.

After a final report exists, create immutable `independent_qa_v7.json` using
`scripts.verify_sec_edgar_iapd_wayback_availability_result_v7`. Only
`PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` may open capture-plan preparation.

## Post-availability tooling

Capture Tooling V4 is the only generation compatible with V7. It recomputes all
115 rows, selects all and only `available=true` rows in original order, and
preserves cohort identities. A verified plan may produce a concrete capture
release whose `not_before` is at least 24 hours after the final V7 report.
Capture Tooling V3 must never be used for V7.

If V7 remains partial, capture stays closed. Preserve every error and create
only a separately frozen exact unresolved-only V8 release after at least
another 24 hours. Availability is not captured text and is never label evidence.

## Other branches

- Existing raw storage remains 278 hash-verified files; this is not completion
  of planned acquisition.
- Historical benchmark train remains 3,916 rows; auxiliary and quarantine stay
  excluded from baseline training.
- Fresh V1-Core remains 0/300 validated groups.
- Crimson AI first-pass work is already complete, but 39 first-human reviews,
  one ready blind second review, 20 waiting second reviews, and 15 official
  reference checks still require people under the frozen protocol.
- DFPI requires a lawful first-party artifact; SSC/HNX require export or reuse
  permission. Verified Vietnamese supply and usable image assets remain zero.

The word TF-IDF logistic model remains a historical internal reference. No new
encoder, chunking, hyperparameter, validation/test opening, promotion, or
deployment is authorized until fresh grouped evidence-backed data passes its
development gates.
