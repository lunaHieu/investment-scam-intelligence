# Reproducibility Current State V8

Date: 2026-10-20
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v10.json`

This guide records the current safe path. It does not authorize live candidate
domain access, labels from availability or registry identity, validation/test
opening, model training, or model scoring.

## Current SEC/IAPD state

- Frozen availability population: 115 rows.
- V8 cumulative result: 113 resolved, 58 available, 55 unavailable, two
  unresolved `EXTERNAL_HOLDOUT` rows.
- V9 remains an exact two-row supplemental availability retry.
- V5 partial-resolved capture plan: exactly 58 rows in original order, split as
  46 `DEVELOPMENT` and 12 `EXTERNAL_HOLDOUT`.
- The two unresolved rows are quarantined and unlabeled.
- Capture release not-before: `2026-10-21T14:19:54.213531+07:00`.

The 12-row holdout portion is an archive-available subset. It is not a random or
representative external holdout and must be reported with that selection limit.

## Capture execution

Before execution, fetch `origin/main`, require a clean tree and local/remote
equality, verify the preparation commit is an ancestor, validate the release
and independent QA hashes, run focused tests, the full suite, and registry
validation. Execute only if neither the final report nor its `.partial` journal
exists.

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_wayback_capture_release_v5 `
  --release configs\sec_edgar_iapd_wayback_capture_release_v5.json `
  --output <temporary-verification-output>

.venv\Scripts\python.exe -m scripts.execute_sec_edgar_iapd_wayback_capture_v1 `
  --release configs\sec_edgar_iapd_wayback_capture_release_v5.json
```

The executor may use only `web.archive.org` raw replay, waits at least 30
seconds per request, makes one attempt per snapshot, stops immediately on HTTP
429, and never overwrites an output. Preserve any partial journal unchanged.

After a complete report exists, independently verify every raw byte and hash
using `scripts.verify_sec_edgar_iapd_wayback_capture_result_v1`. Exact-text
extraction stays closed until that QA passes. A partial capture may lead only to
a separately predeclared missing-row retry after another cooldown.

## Other branches

Existing raw storage remains 278 hash-verified files before this capture; that
count is not the total planned acquisition. Historical baseline train remains
3,916 rows, while fresh V1-Core remains 0/300 validated groups. Crimson and
manual acquisition remain governed by their frozen evidence and permission
contracts.
