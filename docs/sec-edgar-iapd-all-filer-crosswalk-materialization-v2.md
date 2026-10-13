# SEC EDGAR/IAPD all-filer crosswalk materialization V2

## Step name

Materialize the hashed identity review pool.

## Meaning

This step reproduces the universe-wide 0.8 Jaccard and 0.15 runner-up-margin match, enforces unique CIK and unique IAPD host, and writes the expected 1,129 review rows. The raw qualifying-set fingerprint must remain `8f1dd1a471f72bbeb243ef36eecdbec025e6eb981198bc5c0bc34df94cd31fae`.

The pool contains SEC and IAPD names, record identifiers, scores, shared tokens, and a SHA-256 of the normalized host. It does not contain the raw host or candidate URL, cannot be used directly for capture, and creates no ground-truth label. A separate verifier must reproduce the row count, uniqueness, scores, ordering, and fingerprints before any shortlist gate can be prepared.
