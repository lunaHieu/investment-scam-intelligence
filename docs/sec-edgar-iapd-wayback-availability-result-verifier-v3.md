# SEC EDGAR/IAPD Wayback availability result verifier V3

## Step name

Prepare the independent verifier before executing Wayback availability Retry V3.

## Meaning

The verifier is frozen before the network result exists so its acceptance rules cannot be adapted to a favorable outcome. It requires exactly the 115-row plan order, byte-equivalent preservation of all 45 resolved V2 result objects, retries limited to the 70 V2 error rows in their original order, a result timestamp at or after the 24-hour `not_before` gate, exact request aggregates, valid Wayback snapshot evidence, and the unchanged zero-capture safety contract.

A structurally valid partial result may be preserved, but it cannot open capture planning. Only a result with zero unresolved rows receives `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED`. Even that status permits preparation and verification of a separate snapshot-selection plan only; it does not authorize archived HTML download, artifact capture, labeling, validation/test access, or model operations.

The verifier writes its QA artifact without overwrite and performs no network operation.
