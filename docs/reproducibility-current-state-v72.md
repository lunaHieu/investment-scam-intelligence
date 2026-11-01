# Reproducibility Current State V72

- Current direction: `docs/project-direction-plan-r38.md`.
- Offline PBC harness: `scripts/pbc_offline_diagnostic_harness_v1.py`.
- Registration: `registry/analyses/pbc_offline_diagnostic_harness_v1.json`.
- Six synthetic integration tests pass. They use no source responses and
  return no commit values, forbidden key names, or exception messages.
- The harness is not connected to an executor and performs no I/O.
- Current full suite: 1185 passed, 0 failed. Registry validation: 405 analysis
  registries.
- No source request, candidate access, label creation, validation/test access,
  or model operation occurred.
- The PBC diagnostic release remains exhausted; no retry or new request is
  authorized.
- Focused command:
  `.venv\Scripts\python.exe -m unittest tests.test_pbc_offline_diagnostic_harness_v1 -v`
- Current full-suite command:
  `.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10`
