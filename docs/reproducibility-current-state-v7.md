# Reproducibility Current State V7

Date: 2026-10-20  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v9.json`

## Current SEC/IAPD state

- Frozen population: 115 rows in original order.
- V8 result: 113 resolved, 58 available, 55 unavailable, two unresolved.
- V8 made two requests; DNS resolution failed for the first row and the second
  received HTTP 429. Independent QA passed with capture blocked.
- V9 retries exactly the same two `EXTERNAL_HOLDOUT` rows.
- V9 `not_before`: `2026-10-21T14:19:54.213531+07:00`.
- Authoritative executor: `scripts.retry_sec_edgar_iapd_wayback_availability_v9`.

Before execution, require a clean tree, `HEAD == origin/main`, the preparation
commit as an ancestor, matching V8 report/QA hashes, no V8 partial, no V9 final
or partial, focused and full tests, registry validation, release verification,
and successful `--verify-only`.

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v9 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v9.json

.venv\Scripts\python.exe -m scripts.retry_sec_edgar_iapd_wayback_availability_v9 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v9.json `
  --verify-only
```

Only after the gate may `--verify-only` be removed exactly once. A partial
journal is never resumed. Verify a final result with
`scripts.verify_sec_edgar_iapd_wayback_availability_result_v9`.

## Closed downstream gates

Capture Tooling V4 is V7-only; no V9-aware capture tooling is frozen. Capture,
text extraction, grouping, reviews, labels, validation/test access, training,
and model scoring stay closed. Existing Mendeley and external results remain
historical diagnostics, not fresh V1-Core training supply.
