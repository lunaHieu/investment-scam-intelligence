# Reproducibility Current State V13

Date: 2026-10-22  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v15.json`

## Current SEC/IAPD state

The completed retry result, 57 verified captures, 56-row review population,
42 accepted `LEGITIMATE` labels, and 14 retained `UNCERTAIN` records remain
immutable. The same failed replay URL is permanently closed.

The alternate-snapshot CDX V1 release is frozen and independently verified. It
uses one exact target row, excludes timestamp `20260210193325`, uses only
`web.archive.org/cdx/search/cdx`, reserves a crash-safe partial journal, stops
on HTTP 429, and selects metadata through a content- and label-independent
deterministic ordering. Its network gate is
`2026-10-23T23:35:43.595958+07:00`.

Use these current registries:

- `registry/analyses/sec_edgar_iapd_wayback_capture_retry_result_v1.json`
- `registry/analyses/sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1.json`
- `registry/analyses/sec_edgar_iapd_wayback_availability_result_v10.json`
- `registry/analyses/sec_edgar_iapd_owner_acceptance_result_v2.json`

## Reproduction boundary

Before the gate, only `--verify-only`, release verification, tests, registry
validation, and documentation work are permitted. Do not execute CDX early,
do not reuse the consumed owner override, and do not run the failed replay.

After a final CDX report, run the dedicated result verifier. A selected row may
only permit preparation of a separate capture release. It does not create a
raw artifact, label, corpus admission, validation/test access, model score, or
training permission. V1-Core remains 0/300 admitted groups.
