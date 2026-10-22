# A4 — Owner-accepted admission repair protocol V1

Date: 2026-10-23

## Purpose

A4 does not “fill in” missing fields by assumption. It binds the exact 42
owner-accepted SEC EDGAR candidates to their immutable text, capture, grouping
and acceptance evidence, then classifies each admission blocker by the earliest
gate at which it can be resolved safely.

The population is unchanged: 33 development and 9 external-holdout records,
all with an accepted `LEGITIMATE` decision. No `UNCERTAIN` record enters the
protocol. Ordered identity is protected by a SHA-256 digest.

## Nine blockers and their real dependency

| Class | Blocker | What A4 permits |
|---|---|---|
| Human review now | `human_reviewed_language` | Prepare a separate review packet using immutable visible text; language detection may only be a hint |
| Offline evidence packet now | `fresh_cohort_assertion` | Prepare a hash-bound assertion from acquisition namespace and opened-cohort exclusion evidence; no admission credit before independent QA |
| Complete channel only | `channel_contribution_qa_sha256` | Wait for the exact 75-group SEC EDGAR contribution (60 development + 15 holdout) |
| Complete release only | `full_release_cross_partition_exclusion` | Recompute against all 300 groups and all four channels |
| Complete release only | `transitive_group_id` | Assign only after release-wide transitive grouping |
| Complete release plus bounded human review | `case_campaign_group_id` | Review relationships across the full release |
| Complete release plus bounded human review | `entity_domain_family_group_id` | Review relationships across the full release |
| Complete release only | `near_duplicate_group_id` | Run the frozen deterministic rule across the full release |
| Complete release only | `final_release_eligibility` | Set only after all channel contributions and release QA pass |

The existing provisional `technical_group` and the decision
`KEEP_PROVISIONALLY_DISTINCT` are evidence, not final semantic group IDs. They
cannot prove that a record is globally unique relative to candidates that have
not yet been acquired.

## Verified readiness

All 42 records have:

- owner-accepted label provenance;
- minimum visible text and consistent text/raw-capture hashes;
- no opened-cohort overlap or current cross-cohort collision;
- a completed provisional manual group review.

Those facts make the two bounded packets above safe to prepare, but they create
zero admission credit by themselves. A4 creates no repaired candidate manifest,
no partial channel contribution and no V1-Core record. V1-Core therefore
remains 0/300 admitted.

## Next gate

A5 should create two separate, hash-bound offline packets:

1. a language-review packet for the 42 immutable visible-text artifacts; and
2. a fresh-cohort assertion packet derived from the frozen acquisition and
   exclusion chain.

Each needs its own verifier. The remaining seven blockers stay closed until
the required channel or full population exists.
