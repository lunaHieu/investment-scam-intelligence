# SEC/IAPD captured-subset post-capture V2

Date: 2026-10-21
Status: grouping and bounded group/clone review complete; primary artifact review may be prepared

## Meaning of this stage

The 58-row capture produced 57 independently byte-verified artifacts and one
bounded failure. A separately frozen admission release allowed only those 57
verified artifacts to proceed offline while keeping
`TTCV1_EDGAR_AVAIL_DEV_037` in quarantine. This is a 57-row captured subset,
not a claim that the original 58-row capture completed.

Exact-text V2 regenerated all 57 text artifacts byte for byte. Fifty-six met
the frozen minimum-content rule. `TTCV1_EDGAR_AVAIL_DEV_057`
(`manatuckhill.com`) yielded zero visible characters and remains preserved but
is routed out of the reviewable population.

## Grouping result

The 56 reviewable records were compared offline with 107 previously opened
external records and with one another using the frozen exact-host, exact-text,
five-word-shingle and transitive-component rules. Independent recomputation
found:

- no opened-cohort exact, host or near-duplicate overlap;
- no internal grouping edge;
- 56 singleton technical groups; and
- no DEVELOPMENT/EXTERNAL_HOLDOUT collision.

No label was inferred from these results.

## Manual group/clone review

The owner-authorized AI-assisted review inspected the frozen text samples,
contact indicators, declared canonical URLs and automated linkage evidence for
all 56 records. All 56 remain provisionally distinct; no merge or exclusion
was introduced. The review preserved `ground_truth_status=UNCERTAIN` and
`training_eligible=NO` throughout.

The review passed forward three conservative flag classes for primary artifact
review: seven sparse captures below 500 visible characters, one declared
canonical-host mismatch, and one template/placeholder-content indication.
These are review flags, not labels and not evidence of fraud.

## Next gate

Primary artifact review may now be prepared for exactly the 56 group-approved
records. It must combine artifact content with the frozen local EDGAR/IAPD
identity evidence, treat source membership as supporting provenance only, and
recommend `UNCERTAIN` whenever identity, chronology, task relevance,
repurpose/parking or contradiction checks do not all pass. A blind second
review, reconciliation and explicit owner acceptance remain mandatory before
any label materialization.

