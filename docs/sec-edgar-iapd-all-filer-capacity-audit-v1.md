# SEC EDGAR/IAPD all-filer capacity audit V1

## Step name

Audit all-filer identity-linkage capacity at frozen thresholds.

## Meaning

The audit compares 3,668 frozen IAPD identity rows with the 988,519-row SEC all-filer index. It uses the existing tokenization and keeps the Jaccard minimum at 0.8 and the best-versus-runner-up margin at 0.15. CIK and normalized host must both be unique.

Only aggregate counts and a one-way fingerprint of the qualifying set may be written. No identity rows, hosts, candidates, labels, validation/test data, or model operations are emitted by this gate.
