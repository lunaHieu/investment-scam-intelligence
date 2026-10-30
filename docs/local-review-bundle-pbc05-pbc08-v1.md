# Local Review Bundle: PBC05-PBC08 V1

Prepared 2026-10-30 for review before any commit or push. This bundle covers
the complete local change set currently associated with the PBC05-PBC08
postmortem and diagnostic remediation.

## Findings and decisions

- PBC05 remains `PARSER_REJECTED` at PDF section extraction. The exact old
  exception is unrecoverable because the response PDF and exception text were
  intentionally discarded.
- PBC08 remains `PARSER_REJECTED` with the original generic `ValueError`.
  The exact old parser guard is unrecoverable because its response was not
  retained.
- PBC06 and PBC07 are registered as metadata/documentation provenance only.
  No dataset files or rows were admitted; no labels were created.
- The executor/parser remediation adds four fixed PBC08 guard codes and five
  fixed PBC05 PDF codes. It does not retain response bodies or exception text.
- No new network request, retry authorization, evidence acceptance, model
  operation or training action is included.

## Files in this local change set

### Result, review and registration

- `registry/analyses/target_text_corpus_v1_parser_bound_content_supplemental_result_v1.json`
- `registry/analyses/target_text_corpus_v1_pbc05_pbc08_offline_postmortem_v1.json`
- `registry/analyses/target_text_corpus_v1_pbc06_pbc07_success_registration_v1.json`
- `registry/analyses/target_text_corpus_v1_parser_bound_postmortem_and_registration_qa_v1.json`
- `scripts/verify_target_text_corpus_v1_parser_bound_postmortem_and_registration_v1.py`
- `tests/test_target_text_corpus_v1_parser_bound_postmortem_and_registration_v1.py`
- `docs/target-text-corpus-v1-pbc05-pbc08-offline-postmortem-and-pbc06-pbc07-registration-v1.md`

### Parser remediation and verification

- `scripts/execute_target_text_corpus_v1_parser_bound_content_v1.py`
- `scripts/extract_scambench_pdf_sections_v1.py`
- `scripts/process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2.py`
- `scripts/execute_target_text_corpus_v1_parser_bound_content_supplemental_v1.py`
- `tests/test_target_text_corpus_v1_pbc_structured_diagnostics_v1.py`
- `registry/analyses/target_text_corpus_v1_pbc_parser_diagnostic_remediation_v1.json`
- `docs/target-text-corpus-v1-pbc-parser-diagnostics-remediation-v1.md`

### Current-suite lifecycle and project navigation

- `scripts/run_current_test_suite_v9.py`
- `tests/test_current_artifact_lifecycle_v9.py`
- `tests/test_current_test_suite_v9.py`
- `registry/analyses/current_test_suite_lifecycle_v9.json`
- `docs/current-test-suite-lifecycle-v9.md`
- `docs/project-direction-plan-r33.md`
- `registry/analyses/reproducibility_current_state_v67.json`
- `docs/reproducibility-current-state-v67.md`
- `registry/analyses/project_state_gap_ledger_v70.json`
- `docs/project-state-gap-ledger-v70.md`

## Verification performed

- Focused PBC diagnostic, PDF lifecycle and postmortem tests: 9 passed.
- Current suite V9: 1,156 passed.
- Registry validation: passed with 387 analysis registries.
- Remediation implementation SHA-256 pins: all match current files.
- Current reproducibility/ledger/document hashes: all cross-check.
- `git diff --check`: passed.
- Network requests during this review: 0.

## Review limits

This was a local self-review and automated verification, not a second human
review. The historical PBC05/PBC08 causes cannot be recovered offline. The
current code only improves diagnostics for future separately authorized
processing. The local branch is still at `30bf764`, equal to `origin/main`;
these changes are not committed or pushed.
