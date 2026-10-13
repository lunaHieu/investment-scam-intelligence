# SEC EDGAR/IAPD owner-acceptance tooling V1

## Step name

Predeclare explicit owner acceptance and safe label materialization.

## Meaning

Reconciliation does not create ground-truth labels. After the real primary and
blind reviews have been reconciled and independently verified, the project
owner must inspect that frozen reconciliation and provide one explicit Boolean
decision plus a substantive rationale for every record. The acceptance file is
bound to the exact reconciliation SHA-256 and includes an owner attestation.

Only a record already reconciled as `LEGITIMATE` can be accepted. An
`UNCERTAIN` record cannot be promoted through owner acceptance. The acceptance
file is forbidden from supplying or changing `cohort`; cohort is inherited
from the hashed primary-review packet through reconciliation.

Accepted development records become labels but remain
`NO_PENDING_BALANCED_DATASET_RELEASE`. Accepted external-holdout records remain
`NO_EXTERNAL_HOLDOUT` for training and may only be considered after a separate
frozen evaluation release. Independent recomputation must pass before the next
dataset-release step. This stage performs no network, model, or training work.

## Current gate

The tooling is predeclared and tested with synthetic review artifacts. No real
owner acceptance has been created because the capture cooldown is still
closed and no real reconciliation exists. Owner acceptance cannot be inferred
from the earlier authorization to continue the pipeline; it must bind to and
follow inspection of the future concrete reconciliation.
