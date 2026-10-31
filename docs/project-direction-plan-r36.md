# Project Direction Plan R36

## PBC05/PBC08 offline follow-up

The exact-two-row PBC diagnostic result remains immutable. No live request,
response body, PDF, dataset row, or label was used in this follow-up.

- **PBC05:** the observed child returned code 1 with zero stdout. The extractor's
  handled-error path emits a sanitized JSON diagnostic and exits with code 2;
  a synthetic invalid-file check confirmed that behavior. The observed pair is
  therefore inconsistent with a normal handled extraction error. It narrows
  the likely failure boundary to startup/bootstrap or abnormal process exit,
  but does not prove which one. The stderr digest cannot recover the message,
  so the exact cause remains unknown and the exhausted release stays closed.
- **PBC08:** synthetic fixtures confirmed that valid allowlisted commit metadata
  is accepted and unselected fields are dropped. Configured forbidden keys are
  matched recursively and case-insensitively. The live result proves that at
  least one configured key was present, but does not retain which key. A broad
  scan can reject a field such as `message` at any depth; whether that caused
  this row is unknown. Do not change the live result or retry the release.

## Next permitted engineering work

Keep this branch offline. Before any separately authorized request is proposed,
prepare parser-side diagnostics that report only an allowlisted key category
and a sanitized child exception class/stage. Add synthetic tests for those
diagnostics first. No parser policy change should reinterpret PBC08 without
the original response or a new, separately scoped source result. Do not repeat
PBC05/PBC08 under the exhausted release.

Evidence and test details: `registry/analyses/target_text_corpus_v1_pbc_offline_followup_v1.json`.

All evidence-acceptance, acquisition, validation/test access, and model gates
remain closed.
