# Dataset V1-Core capacity matrix V4 (A3)

Date: 2026-10-23

## What the denominator means

V1-Core is a **fresh text corpus of 300 disjoint groups**, not a count of every
row or file currently stored. Its accepted artifact is visible text extracted
from archived website HTML. The four frozen channels each contribute 75 groups:
60 development and 15 untouched external holdout.

The project therefore has three different supply layers which must not be
combined:

- **admitted V1-Core:** 0/300 groups;
- **owner-accepted conditional candidates:** 42/300 (33 development and 9
  holdout, all in the SEC EDGAR-linked `LEGITIMATE` channel);
- **historical/reference/discovery material:** useful for baselines or finding
  candidates, but contributes zero V1-Core groups.

The 42 accepted decisions are not lost. They remain valid conditional supply,
but all 42 still lack the complete channel, language, grouping, fresh-cohort and
full-release exclusion fields required by the release contract. Until those
fields and the complete balanced release pass QA, contractual progress remains
0/300.

## Exact gap

| Channel | Development target | Admitted | Conditional supply | Conditional gap | Holdout target | Admitted | Conditional supply | Conditional gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CONFIRMED regulator-linked | 60 | 0 | 0 | 60 | 15 | 0 | 0 | 15 |
| CONFIRMED CFTC RED-linked | 60 | 0 | 0 | 60 | 15 | 0 | 0 | 15 |
| LEGITIMATE IAPD/register-linked | 60 | 0 | 0 | 60 | 15 | 0 | 0 | 15 |
| LEGITIMATE SEC EDGAR-linked | 60 | 0 | 33 | 27 | 15 | 0 | 9 | 6 |

Strictly, the release gap is still all 300 groups. For acquisition planning
only, if all 42 accepted candidates later pass the full contract, the residual
gap is 258 groups: 207 development and 51 holdout. By label this is 150
`CONFIRMED` groups and 108 `LEGITIMATE` groups.

## Language overlay

The matrix requires at least 30 human-reviewed non-English groups, including at
least 16 Vietnamese groups. The split is:

- development: 12 non-English per label, including 6 Vietnamese per label;
- holdout: 3 non-English per label, including 2 Vietnamese per label.

Audited language credit is still zero. Source country, host, registry identity
and text heuristics cannot supply this field. English has no independent
minimum quota; it is the residual after the non-English minima, so there is no
defensible “English shortage” number before language review.

## What existing assets do and do not contribute

| Asset layer | Current amount | V1-Core credit | Reason |
|---|---:|---:|---|
| Historical Mendeley baseline train | 3,916 rows | 0 | Existing internal baseline, explicitly excluded from fresh quotas |
| Integrity-verified raw store | 278/278 files | 0 | File-integrity denominator, not accepted-group denominator |
| Crimson domain inventory | 43,572 domains | 0 | Unlabeled discovery metadata without accepted text artifacts or ground truth |
| Usable image assets | 0 | 0 | No compatible image corpus exists; image is outside the text-only V1-Core contract |
| SEC/IAPD reviewable text | 56 records | 0 admitted | 42 accepted conditional candidates; 14 remain `UNCERTAIN` |

Absence of image assets does not block the text-only V1-Core release. It blocks
only a later multimodal branch. Likewise, the Crimson inventory may guide a
separately governed discovery workflow but cannot be converted into training
rows by counting domains or using anomaly scores.

## Priority order

1. Preserve and repair the nine missing admission fields for the 42 accepted
   SEC EDGAR candidates; do not call this a partial release.
2. Execute separately frozen source waves for the two currently enumerable
   empty channels: regulator-linked `CONFIRMED` and IAPD-linked `LEGITIMATE`.
3. Acquire the residual 33 SEC EDGAR-linked groups using fresh, disjoint
   identities.
4. Keep the 75-group CFTC RED deficit blocked until a documented lawful source
   capacity route exists; no other channel may silently subsidize it.
5. Apply the Vietnamese/non-English overlay to every wave and credit language
   only after human review of captured visible text.

This A3 matrix is offline planning only. It enumerates no new candidate, makes
no network request, changes no label, opens no validation/test data and permits
no training or scoring.
