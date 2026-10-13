# SEC EDGAR/IAPD exact-text tooling V1

## Step name

Predeclare offline exact-text extraction and independent regeneration.

## Meaning

Only a complete capture result whose raw bytes passed independent SHA-256 QA can
enter this stage. The release pins that report and QA, the immutable text root,
manifest and report. Extraction decodes archived transport bytes, extracts
visible text with the project-standard deterministic parser, writes exact UTF-8
without an added newline, hashes raw, decoded and text bytes, preserves declared
canonical URLs, and retains development/holdout identity.

Every output remains `UNCERTAIN`, `training_eligible=NO`, and
`model_scoring_eligible=NO`. Text below 20 non-whitespace characters is preserved
but routed out of the reviewable set rather than silently dropped or replaced.

The independent result verifier re-runs decoding and extraction from the frozen
raw captures, compares every manifest field and output byte, and rejects extra or
missing text files. Only byte-for-byte QA may release preparation of offline
grouping and exclusion checks; it does not release labeling or model use.

## Current gate

The tooling has been tested with synthetic capture artifacts only. The real V3
availability result, capture plan, raw capture result and complete capture QA do
not yet exist, so no real extraction release or text output has been created.
There are zero network operations in this stage.
