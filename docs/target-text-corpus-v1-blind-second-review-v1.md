# Target text corpus v1: blind second review

## Purpose

This gate creates a separate review pass over all 22 frozen evidence items. Its packet contains the same artifact text and official evidence used by the primary review, but it replaces candidate IDs with opaque blind IDs and omits source strata, group-review notes, every primary judgment, and every primary summary.

## Reviewer isolation

The second reviewer may read only the blind packet. The reviewer must not open the private ID mapping, the primary result registry, the primary review output, model predictions, validation data, or test data. No network access is allowed.

## Decisions

The reviewer independently records `CONFIRMED`, `LEGITIMATE`, or `UNCERTAIN` under the same conservative evidence rules. Every item needs five explicit assessments, at least two supporting facts, a substantive rationale, and uncertainty reasons where applicable. Recommendations remain non-labels and every row remains ineligible for training.

## Exit gate

The second review must cover each opaque ID exactly once and pass structural and blinding QA. Only after that output is frozen may the private mapping be used to compare it with the primary review. Disagreements must be reconciled explicitly; agreement alone still does not create a label without owner acceptance.
