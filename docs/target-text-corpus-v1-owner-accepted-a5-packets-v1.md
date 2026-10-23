# A5 — Owner-accepted admission packets V1

Date: 2026-10-23

## Purpose

A5 prepares the two exact-population artifacts authorized by A4 without
claiming that either artifact is a partial Dataset V1-Core release. Both
packets preserve the ordered identity of 42 owner-accepted SEC EDGAR records:
33 development and 9 external-holdout records.

## Language-review packet

Every task points to the immutable extracted visible-text file and records its
SHA-256 and non-whitespace character count. The builder deliberately leaves
`language_code` empty, sets `human_reviewed_language=false`, provides no
automatic hint and marks all 42 tasks `PENDING_HUMAN_LANGUAGE_REVIEW`.

This avoids treating AI or automatic language detection as a human decision.
The independent verifier re-hashes every visible-text file and confirms that
no language decision, label change or admission credit was prefilled.

## Fresh-cohort assertion packet

Every assertion is independently bound to the frozen `TTCV1_EDGAR_AVAIL`
acquisition namespace, its availability-plan identity, exact text and raw
capture hashes, the opened-cohort exclusion result, the absence of a
development/holdout collision and the provisional manual group decision.

The assertion packet may state `fresh_cohort=true` because that specific fact
is recomputed from the frozen evidence chain. It is not a V1-Core record and
creates zero admission credit. Final release-wide grouping and eligibility
remain unresolved.

## Gates preserved

A5 performs no network access, live-domain access, capture, label change,
validation/test opening, scoring or training. It creates no repaired candidate
manifest and no partial channel contribution. Seven release-wide blockers
remain closed, and the language blocker remains pending actual human review.
