# Reproducibility Current State V71

- Current direction: `docs/project-direction-plan-r37.md`.
- Diagnostic contract: `scripts/pbc_safe_diagnostic_contract_v1.py`.
- Registration: `registry/analyses/pbc_safe_diagnostic_contract_v1.json`.
- Eight synthetic tests pass. They cover category-only forbidden-key output,
  allowlisted exception classes, generic fallback classes, stage/code
  normalization, and bounded stream parsing.
- The current full suite passes 1177/1177; registry validation passes with 402
  analysis registries.
- The helper performs no I/O and is not connected to an executor.
- No source endpoint request, raw response retention, label change, validation
  or test access, or model operation occurred.
- Same-release PBC retry and new source requests remain unauthorized.
- Focused command:
  `.venv\Scripts\python.exe -m unittest tests.test_pbc_safe_diagnostic_contract_v1 -v`
- Current full-suite command remains:
  `.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10`
