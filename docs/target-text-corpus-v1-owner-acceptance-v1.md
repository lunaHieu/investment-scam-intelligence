# Target Text Corpus V1: owner acceptance

The project owner authorized continuation after receiving the audited project-state report that named hash-bound acceptance of the 22 reconciled recommendations as the next gate. The acceptance does not claim that the owner independently re-reviewed every evidence item.

The frozen reconciliation is adopted without changing its recommendations:

- 4 `CONFIRMED` ground-truth labels materialized;
- 11 `LEGITIMATE` ground-truth labels materialized;
- 7 `UNCERTAIN` records retained without a binary label;
- 0 records made eligible for training, model selection, or threshold tuning.

All 22 records belong to an already-opened schema-review pilot. Under the frozen target-corpus protocol, they remain diagnostic-only and contribute zero rows to future fitting or model selection. Owner acceptance and training eligibility are deliberately separate gates.

The next permitted research step is to freeze the Dataset V1-Core sampling matrix and source quotas for a fresh cohort. That matrix must target at least 120 `CONFIRMED` and 120 `LEGITIMATE` development groups, at least two acquisition channels per label, no more than 50% from one channel, and a separate untouched 30+30 external holdout.

No model was fitted or scored, and no validation, internal-test, or external-holdout partition was opened in this step.
