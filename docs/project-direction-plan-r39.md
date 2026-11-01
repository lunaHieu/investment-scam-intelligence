# Project Direction Plan R39

## Offline executor-candidate preflight

Added `scripts/verify_pbc_diagnostic_executor_preflight_v1.py`, a pure
candidate-package verifier. It checks a future V2 package without sending
requests or creating release files. The verifier always returns
`network_execution_allowed: false`, even when the synthetic package is
internally consistent.

The preflight requires a new release identity, the immutable prior-result hash,
row-specific technical rationale codes, the current safe-diagnostic tooling
hashes, exact endpoint identities, independently bound QA and owner scope,
one request per row, 60-second pacing, disabled redirects/retry/resume,
no-overwrite, fail-closed stop policy, timezone-aware timestamps, and new
nonexistent output paths. The `not_before` timestamp cannot precede release
creation.

Ten synthetic preflight tests pass. Fixtures are ephemeral test objects; no
candidate release, QA, or owner authorization file was created. The PBC V1
release and result remain immutable. Any real future request still needs a
separately prepared and independently checked package plus a distinct
execution gate.

Evidence: `registry/analyses/pbc_diagnostic_executor_preflight_v1.json`.

Acquisition, evidence acceptance, validation/test access, scoring, and training
remain closed.
