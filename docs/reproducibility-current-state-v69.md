# Reproducibility Current State V69

- Current direction: `docs/project-direction-plan-r35.md`.
- Diagnostic result for PBC05/PBC08 is independently verified and immutable.
- Outcomes: 0 success, 2 parser rejections, 0 HTTP errors, 0 transport errors.
- PBC05: same response hash as its prior attempt; `SECTION_EXTRACTION` failed
  again with zero stdout bytes. Exact cause remains unknown.
- PBC08: parser guard `FORBIDDEN_DATASET_KEY_PRESENT`; the key name was not
  retained.
- No raw response or dataset files were retained, and no rows or labels were
  created. The exact-two-request release is exhausted; no retry is authorized.
- Dataset acquisition, evidence acceptance, validation/test access and model
  operations remain closed.
