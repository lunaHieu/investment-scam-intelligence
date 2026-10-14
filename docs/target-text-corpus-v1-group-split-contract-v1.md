# Dataset V1-Core deterministic group-split contract V1

## Step name

Predeclare the metadata-only development group split and external-holdout seal.

## Meaning

After a real 300-group V1-Core release passes independent QA, only its 240
development groups may enter this planner. Groups are stratified by target
status and acquisition channel. Each 60-group stratum is ranked by a frozen
SHA-256 key built from the seed, development namespace, target status, channel,
record ID, and transitive group ID. The first 42 become train assignments, the
next 9 validation assignments, and the final 9 internal-test assignments.

Across four channels the exact totals are therefore 168 train, 36 validation,
and 36 internal test. The ranking never uses visible text, language, source
URL, raw capture bytes, model scores, or predictions. Each assignment includes
only metadata and a commitment to the complete frozen source record.

The 60 external-holdout records are not included in the assignment list. The
plan records only their count and a deterministic population commitment. Their
record IDs, text, labels, and group metadata remain absent from the split plan.

## Closed gates

A passing independent reconstruction freezes assignments but does not
materialize any partition. A separate train-materialization release is still
required. Validation, internal test, and external holdout remain unopened, and
no model may be trained or scored in this step.

## Current state

The builder and verifier are tested against a synthetic balanced 300-group
manifest. No real split assignment, partition file, or model-access permission
has been created.
