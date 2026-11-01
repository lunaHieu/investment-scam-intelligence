# Project Direction Plan R37

## Safe parser diagnostics prepared offline

Added `scripts/pbc_safe_diagnostic_contract_v1.py` as a separate, pure offline
utility. It does not alter the frozen PBC parser, old results, or QA:

- PBC08 forbidden fields produce only a bounded category label. The helper
  discards key names, paths, and values; unknown configured keys collapse to
  `UNKNOWN_CONFIGURED_KEY`.
- PBC05 child diagnostics accept only known stages, known extractor codes, and
  a small exception-class allowlist. Other classes collapse to
  `OTHER_EXCEPTION`. Only byte counts and SHA-256 values are retained.
- Child stdout is parsed only up to 64 KiB. Exception classification reads at
  most the final 4 KiB of stderr. Neither stream text is returned.
- Eight synthetic tests pass. The full suite passes 1177/1177 and registry
  validation passes with 402 analysis registries. No real PDF, source response,
  or source endpoint was used.

This module is **not wired into a network executor** and grants no retry or
source-request permission. Integrating it into any future acquisition attempt
requires a new versioned parser/executor, independent tests, and its own
scoped release. Never rerun the exhausted PBC05/PBC08 release.

Evidence: `registry/analyses/pbc_safe_diagnostic_contract_v1.json`.

All acquisition, evidence acceptance, validation/test access, and model gates
remain closed.
