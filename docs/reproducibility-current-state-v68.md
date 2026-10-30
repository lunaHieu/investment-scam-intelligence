# Reproducibility Current State V68

- Current direction: `docs/project-direction-plan-r34.md`.
- A diagnostic-only release for PBC05 and PBC08 is prepared and passes its
  offline release verifier.
- The immutable prior PBC05-PBC08 result is pinned; the new release is limited
  to two GETs maximum, one attempt per row, with at least 30 seconds between
  requests.
- No network execution is authorized by this preparation. Execution requires
  committed tooling, an independent result verifier, and separate owner
  authorization.
- Dataset download, evidence acceptance, labeling, validation/test access and
  training remain closed.
