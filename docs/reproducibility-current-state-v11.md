# Reproducibility Current State V11

Date: 2026-10-22  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v13.json`

## Current SEC/IAPD entry point

The V10 availability retry executed once after its gate and stopped on HTTP
429 after one request. Independent QA confirms that all 113 previously
resolved rows remain unchanged and the two external-holdout errors remain
quarantined. V10 is immutable and must not be rerun.

Completed downstream work is also unchanged:

- 57 of 58 planned archive captures are byte/hash verified;
- 56 records completed grouping and two-pass evidence review;
- owner acceptance retained 42 `LEGITIMATE` labels and 14 `UNCERTAIN` rows;
- no SEC/IAPD record is currently training-eligible or scoring-eligible.

Use these current registries:

- `registry/analyses/sec_edgar_iapd_wayback_availability_result_v10.json`
- `registry/analyses/sec_edgar_iapd_wayback_capture_result_v1.json`
- `registry/analyses/sec_edgar_iapd_review_reconciliation_v2.json`
- `registry/analyses/sec_edgar_iapd_owner_acceptance_result_v2.json`

## Next timed action

The one-row capture retry release remains frozen and unchanged. It was not run
after the V10 rate limit. The next archive-network action is conservatively
deferred until at least `2026-10-23T18:32:45.434853+07:00`. At that time the
repository, release, independent QA, output absence, and full test suite must
all be rechecked before execution.

Any future retry of the two unresolved availability rows requires a new
separately frozen release. It must not alter the completed 58-row capture plan
or the accepted 56-row review snapshot.

## Dataset and model gates

The 33 accepted development `LEGITIMATE` candidates remain verified supply,
not an admitted V1-Core release. V1-Core remains 0/300 admitted groups because
the balanced class, holdout, channel, language, grouping, and provenance gates
are not met. Validation/test access, model scoring, and training remain closed.
