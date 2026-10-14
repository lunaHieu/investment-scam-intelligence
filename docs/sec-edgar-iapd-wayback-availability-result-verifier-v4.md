# SEC EDGAR/IAPD Wayback availability result verifier V4

## Step name

Predeclare the independent verifier for Wayback availability Retry V4.

## Meaning

The verifier is frozen before the V4 network result exists. It requires the
original 115-row plan order, byte-equivalent preservation of all 84 resolved V3
objects, retries limited to the 31 V3 error rows in original order, a result
timestamp at or after the cooldown gate, exact request aggregates, valid Wayback
snapshot evidence, and the unchanged zero-capture safety contract.

A structurally valid partial result remains preserved but cannot open capture
planning. Only zero unresolved rows receives
`PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED`; this permits preparation of a
separate capture plan only. It does not authorize archived HTML download,
artifact capture, labels, validation/test access, or model operations.

The verifier writes its QA artifact without overwrite and performs no network
operation.
