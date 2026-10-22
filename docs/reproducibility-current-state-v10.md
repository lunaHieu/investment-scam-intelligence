# Reproducibility Current State V10

Date: 2026-10-22  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v12.json`

## Current SEC/IAPD entry point

The original 58-row archive plan has completed with 57 byte/hash-verified
captures and one quarantined short-body failure. The captured-subset pipeline
then produced 57 exact-text records, routed one empty-text record out, and
completed grouping plus two-pass evidence review for 56 records.

Owner acceptance V2 is immutable and independently verified:

- 42 accepted `LEGITIMATE` labels: 33 `DEVELOPMENT`, 9
  `EXTERNAL_HOLDOUT`;
- 14 retained `UNCERTAIN` records: 11 `DEVELOPMENT`, 3
  `EXTERNAL_HOLDOUT`;
- 0 training-eligible records and 0 scoring-eligible records.

Use these current registries:

- `registry/analyses/sec_edgar_iapd_wayback_capture_result_v1.json`
- `registry/analyses/sec_edgar_iapd_captured_subset_post_capture_v2.json`
- `registry/analyses/sec_edgar_iapd_review_reconciliation_v2.json`
- `registry/analyses/sec_edgar_iapd_owner_acceptance_result_v2.json`

## Independent timed gates

The two-row V10 availability retry remains closed until
`2026-10-22T18:18:58.983066+07:00`. The exact one-row missing-capture retry
remains closed until `2026-10-22T23:08:09.711801+07:00`. Neither retry may
overwrite, resume, or relabel the completed 56-row review population.

## Dataset and model gates

The accepted 33 development `LEGITIMATE` candidates are verified supply, not a
balanced V1-Core release. V1-Core remains 0/300 admitted groups because the
full 120+120 development and 30+30 holdout balance, channel quotas, Vietnamese
coverage, grouping, and release QA are not met. Validation, test, training,
model scoring, and candidate live-domain access remain closed.

The next offline step is a capacity-gap update that counts these 33 candidates
without weakening the frozen V1-Core contract. Historical model experiments
remain separate and must not consume this partial cohort.
