# SEC/IAPD evidence review and reconciliation V2

Date: 2026-10-21
Status: independently reconciled recommendations; owner acceptance required

## Reviewed population

The review stack covers exactly 56 captured-subset records that passed the
minimum-content and group/clone gates. One captured row with empty extracted
text remains outside review, and one failed capture remains quarantined. The
original 58-row plan has not been represented as complete.

## Primary review

The owner-authorized primary reviewer inspected each captured artifact with
the frozen local EDGAR/IAPD evidence. The result was 47 `LEGITIMATE`
recommendations and 9 `UNCERTAIN` recommendations. Every recommendation
remained `ground_truth_status=UNCERTAIN`, `label_created=false`, and
`training_eligible=NO`.

## Blind second review

An independent reviewer received a packet containing the same artifact and
official evidence but no primary recommendations, assessments, rationales or
summary. The reviewer did not use network access, live candidate domains,
model predictions, or source membership as ground truth. The result was 44
`LEGITIMATE` and 12 `UNCERTAIN` recommendations.

The first structural-QA attempt correctly failed because the independent
reviewer represented packet and reviewer metadata at the top level rather than
inside the verifier's expected nested objects. The immutable review artifact
was not changed. A versioned verifier compatibility correction accepted both
equivalent layouts, and attempt 2 passed all population, decision and safety
checks. Both QA attempts are retained.

## Reconciliation

Reconciliation was deterministic and conservative:

- two `LEGITIMATE` recommendations produce a `LEGITIMATE` recommendation;
- any reviewer `UNCERTAIN` produces `UNCERTAIN`; and
- every reviewer disagreement produces `UNCERTAIN`.

The resulting 56-row snapshot contains 42 reconciled `LEGITIMATE`
recommendations and 14 `UNCERTAIN` recommendations. Seven rows had reviewer
disagreement and were routed to `UNCERTAIN`. All 56 rows still have owner
acceptance pending; no ground-truth label or training eligibility exists.

## Required next decision

The owner must inspect and accept or reject the frozen reconciliation snapshot.
Acceptance must not include the one below-minimum row or the one failed-capture
row. Only a separately versioned owner-acceptance artifact may authorize label
materialization, and EXTERNAL_HOLDOUT identities must remain excluded from
training even after acceptance.

