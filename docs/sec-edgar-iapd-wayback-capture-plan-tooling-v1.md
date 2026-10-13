# SEC EDGAR/IAPD Wayback capture-plan tooling V1

## Step name

Predeclare exact snapshot-plan construction and independent verification.

## Meaning

This gate fixes how a future complete availability V3 result is converted into a
capture plan. It prevents a convenient subset from being selected after the
availability outcome is known. The builder includes every and only V3 row with
`available=true`, preserves V3 order and the `DEVELOPMENT` / `EXTERNAL_HOLDOUT`
identity, pins the exact raw-replay URL, and assigns a non-overwriting path below
the project raw-data root.

The builder fails closed unless the availability result contains exactly 115
resolved rows and its independently produced QA has status
`PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED`. Partial V3 results, unresolved
errors, a changed evidence hash, unexpected cohort, unsafe path, duplicate ID,
or existing capture target all block plan creation.

The independent verifier reconstructs the expected population directly from
the availability result, checks every field in order, verifies the release,
availability and QA hashes, checks raw Wayback replay URLs and path containment,
and confirms the unavailable count. Synthetic tests cover both cohorts, exact
membership and rejection of a partial result.

## Current gate

The tooling is frozen before the V3 result exists. It performs no network
operation and creates no plan, capture, text, label, score, or training record.
A passing plan QA will permit preparation of a separate hash-bound execution
release; it will not itself authorize download. The actual population size is
deliberately unknown until V3 resolves all 115 rows.

Planned immutable outputs after V3 passes:

- `D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_capture_plan_v1\capture_plan_v1.json`
- `D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_capture_plan_v1\independent_qa_v1.json`

Live candidate domains, archived HTML download, label decisions, model
operations, validation/test access and training remain closed.
