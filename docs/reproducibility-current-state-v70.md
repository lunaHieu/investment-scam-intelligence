# Reproducibility Current State V70

- Current direction: `docs/project-direction-plan-r36.md`.
- Offline PBC follow-up: `registry/analyses/target_text_corpus_v1_pbc_offline_followup_v1.json`.
- Five synthetic boundary tests pass. They use no network and no original
  response body.
- Three hash-pinned current-state/analysis registry tests pass. The project
  full suite passed 1167/1167; registry validation passed with 399 analysis
  registries.
- PBC05's exact cause remains unrecoverable: return code 1 and zero stdout do
  not match the extractor's tested handled-error output, but retained hashes
  cannot distinguish bootstrap failure from abnormal termination.
- PBC08's configured forbidden-key scan is recursive and case-insensitive.
  Synthetic valid commit metadata passes; each configured forbidden key is
  rejected. The exact key in the live response remains unknown.
- The exact-two-request diagnostic release is exhausted. No retry or new
  source request is authorized by this analysis.
- Candidate-domain operations: 0; raw responses retained: 0; labels created: 0;
  validation/test rows opened: 0; model operations: 0.
- Focused command:
  `.venv\Scripts\python.exe -m unittest tests.test_target_text_corpus_v1_pbc_offline_boundary_review_v1 -v`
- Current full-suite command remains:
  `.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10`
