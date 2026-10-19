# Reproducibility Current State V6

Date: 2026-10-19  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v8.json`

This guide records the current safe path. It does not authorize live candidate
domain access, labeling from availability or registry membership, validation or
test opening, model training, or model scoring.

## Current SEC/IAPD state

- Availability plan: 115 rows in frozen order.
- V7 result: 113 resolved, 58 available, 55 unavailable, two unresolved.
- V7 attempted seven rows and stopped on HTTP 429; independent QA passed with
  errors preserved and capture blocked.
- V8 retries exactly the two remaining IDs, both `EXTERNAL_HOLDOUT`.
- V8 `not_before`: `2026-10-20T14:06:35.423170+07:00`.
- Authoritative module: `scripts.retry_sec_edgar_iapd_wayback_availability_v8`.
- Final and partial V8 outputs are both terminal no-overwrite states.

Before execution, fetch `origin/main`, require a clean tree and local/remote
equality, verify the pinned preparation commit is an ancestor, run the V8
release verifier, `--verify-only`, focused tests, the full suite, and registry
validation. Execute only when neither `availability_report_v8.json` nor its
`.partial` journal exists. Never resume a partial journal.

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v8 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v8.json

.venv\Scripts\python.exe -m scripts.retry_sec_edgar_iapd_wayback_availability_v8 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v8.json `
  --verify-only
```

At or after the gate, remove `--verify-only` exactly once. The executor reserves
a journal before the first request, checkpoints every logical attempt, waits at
least 60 seconds between candidates, and stops immediately on HTTP 429.

After a final report exists, create immutable `independent_qa_v8.json` using
`scripts.verify_sec_edgar_iapd_wayback_availability_result_v8`. Only
`PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` may open preparation of a new
V8-aware capture tooling release.

## Post-availability tooling

Capture Tooling V4 is pinned to V7 and must not consume V8. No V8-aware capture
plan or execution release is currently frozen. If V8 completes, separately
build, test, register, and independently verify the V8-aware tooling before
constructing any plan. A verified plan would still require a concrete capture
release with its own cooldown before capture.

If V8 remains partial, capture stays closed. Preserve every error and create
only a separately frozen exact unresolved-only retry after at least another 24
hours. Availability is not captured text and is never label evidence.

## Other branches

- Existing raw storage remains 278 hash-verified files; this is not completion
  of planned acquisition.
- Historical benchmark train remains 3,916 rows; auxiliary and quarantine stay
  excluded from baseline training.
- Fresh V1-Core remains 0/300 validated groups.
- Crimson AI first-pass work is complete, but human and official-reference
  follow-ups remain governed by the frozen review protocol.
- DFPI requires a lawful first-party artifact; SSC/HNX require export or reuse
  permission. Verified Vietnamese supply and usable image assets remain zero.

The word TF-IDF logistic model remains a historical internal reference. No new
encoder, chunking, hyperparameter, validation/test opening, promotion, or
deployment is authorized until fresh grouped evidence-backed data passes its
development gates.
