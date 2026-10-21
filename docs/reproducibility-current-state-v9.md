# Reproducibility Current State V9

Date: 2026-10-21
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v11.json`

## Current SEC/IAPD entry point

V9 is immutable and independently verified as partial after HTTP 429. Use:

- `registry/analyses/sec_edgar_iapd_wayback_availability_result_v9.json`
- `registry/analyses/sec_edgar_iapd_wayback_availability_retry_release_v10.json`
- `configs/sec_edgar_iapd_wayback_availability_retry_release_v10.json`

Do not rerun V9. Do not execute V10 before
`2026-10-22T18:18:58.983066+07:00`. The V5 capture plan/release remains the
only authorized capture population and stays exactly 58 rows.

At the next gate, run repository tests, registry validation, the V10 release
verifier and both executor `--verify-only` checks. Execute V10 once only if no
V10 final or partial exists. If V10 avoids HTTP 429, execute the unchanged V5
archive-only capture. A partial output is never auto-resumed.

After complete capture QA, use the already verified compatible exact-text V1
and grouping V1 stack. Preserve below-minimum text but route it out; exclude
prior-opened overlap and any holdout-development collision.

Validation, test, training, scoring, live candidate-domain access and automatic
labels remain closed. Historical train remains 3,916 rows; fresh V1-Core
remains 0/300 admitted groups.
