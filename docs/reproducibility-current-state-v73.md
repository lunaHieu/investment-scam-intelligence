# Reproducibility Current State V73

- Current direction: `docs/project-direction-plan-r39.md`.
- Offline preflight verifier:
  `scripts/verify_pbc_diagnostic_executor_preflight_v1.py`.
- Registration:
  `registry/analyses/pbc_diagnostic_executor_preflight_v1.json`.
- Ten synthetic tests check both a consistent candidate package and fail-closed
  mutations. A consistent package still cannot open network execution.
- Fixtures were in-memory only. No release, QA, or owner authorization was
  created for an actual request.
- The prior PBC diagnostic release remains exhausted and immutable.
- Current full-suite and registry-validation counts are recorded in the
  hash-pinned registry after final verification.
- Focused command:
  `.venv\Scripts\python.exe -m unittest tests.test_verify_pbc_diagnostic_executor_preflight_v1 -v`
- Current full-suite command:
  `.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10`
