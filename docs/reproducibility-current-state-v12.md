# Reproducibility Current State V12

Date: 2026-10-22  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v14.json`

## Current SEC/IAPD state

The one-row capture retry is complete and immutable. It used the
policy-compliant V2 executor once, received HTTP 200, and reproduced the same
42-byte below-minimum response. Independent V2 QA passed with quarantine
preserved. The same replay URL must not be requested again.

Current material counts remain:

- availability: 113/115 resolved, with two external-holdout errors;
- capture: 57/58 verified, with one development row quarantined;
- review: 56 completed two-pass records;
- owner acceptance: 42 `LEGITIMATE`, 14 `UNCERTAIN`;
- training/scoring eligibility: zero.

Use these current registries:

- `registry/analyses/sec_edgar_iapd_wayback_capture_retry_result_v1.json`
- `registry/analyses/sec_edgar_iapd_wayback_availability_result_v10.json`
- `registry/analyses/sec_edgar_iapd_owner_acceptance_result_v2.json`

## Next safe branches

For the failed capture, only a separately frozen CDX enumeration of alternate
snapshots is justified. Any alternate artifact must follow a supplemental
exact-text/grouping/review path and cannot modify the frozen 56-row snapshot.

For availability, V10 must not be rerun. V11 requires new tooling that follows
the current Internet Archive User-Agent policy and preserves HTTP 429 headers.

V1-Core remains 0/300 admitted groups. Validation/test access, model scoring,
and training remain closed.
