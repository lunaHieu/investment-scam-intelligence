# Dataset V1-Core train-only materialization contract V1

## Step name

Predeclare the train-only release, execution, and independent result QA.

## Meaning

After a real deterministic split passes independent QA, the release selects
only its 168 `train` assignments: 84 `CONFIRMED`, 84 `LEGITIMATE`, and exactly
42 records from each acquisition channel. It contains commitments and audit
metadata but no visible text. An independent reconstruction must pass before
execution.

Execution joins the committed train assignments back to the frozen V1-Core
manifest and verifies every complete-record commitment. It emits one JSONL
dataset with exactly four fields: `record_id`, `text_content`, `label`, and
`group_id`. `CONFIRMED` maps to 1 and `LEGITIMATE` maps to 0. Channel and
provenance metadata remain in a separate audit report and cannot become model
features accidentally.

Validation, internal-test, and external-holdout records are absent from both
the release and the materialized dataset. Output files are immutable and the
independent result verifier reproduces their rows and bytes exactly.

## Closed model gates

A verified train-only dataset still does not authorize fitting. The next gate
must freeze a model-development protocol covering preprocessing, grouped OOF
evaluation, metrics, thresholds, source-predictability diagnostics, seed, and
compute limits. Validation, internal test, and external holdout remain closed.

## Current state

All stages are tested using a synthetic balanced V1-Core release. No real
train dataset was created and no model operation was performed.
