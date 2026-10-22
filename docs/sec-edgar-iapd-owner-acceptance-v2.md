# SEC/IAPD owner acceptance V2

Date: 2026-10-22  
Status: owner acceptance materialized and independently verified; dataset and model gates remain closed

## Step name and meaning

This step records the project owner's explicit acceptance of the frozen
56-record reconciliation snapshot. It converts only the 42 reconciled
`LEGITIMATE` recommendations into evidence-backed labels. It does not admit a
record to Dataset V1-Core, open a model partition, authorize training, or
authorize scoring.

The authorization was given after the owner received the concrete result: 42
`LEGITIMATE`, 14 `UNCERTAIN`, and seven reviewer disagreements. It does not
claim that the owner independently repeated the primary or blind evidence
review.

## Verified result

- 42 `LEGITIMATE` labels materialized: 33 `DEVELOPMENT` and 9
  `EXTERNAL_HOLDOUT`.
- 14 records remain unlabeled `UNCERTAIN`: 11 `DEVELOPMENT` and 3
  `EXTERNAL_HOLDOUT`.
- The 9 accepted `EXTERNAL_HOLDOUT` records remain
  `NO_EXTERNAL_HOLDOUT` for training.
- The 33 accepted development records remain
  `NO_PENDING_BALANCED_DATASET_RELEASE`.
- Training-eligible records: 0.
- Model-scoring-eligible records: 0.

One failed capture and one captured row below the text minimum were never part
of this owner-acceptance population. Their quarantine and retry contracts are
unchanged.

## Integrity controls

The pending packet, completed acceptance, materialized result, and independent
QA are separate no-overwrite artifacts. Every artifact is bound to the exact
reconciliation and QA SHA-256 values. The verifier independently regenerates
the materialized output and enforces the frozen 42/14 partition, the 33/9
accepted cohort counts, the 11/3 uncertain cohort counts, and the prohibition
against training on external holdout records.

## Next gate

The 33 accepted development records are verified supply toward the
`LEGITIMATE` side of the future V1-Core corpus, not a standalone balanced
release. The V1-Core contract still requires 120 `LEGITIMATE` and 120
`CONFIRMED` development groups plus a separate 30+30 external holdout and
channel/language constraints. Therefore the next safe step is a hash-bound
capacity-gap update and acquisition plan; no real V1-Core split or training
materialization may run yet.
