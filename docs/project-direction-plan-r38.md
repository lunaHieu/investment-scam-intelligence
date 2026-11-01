# Project Direction Plan R38

## Fixture-only integration harness

Added `scripts/pbc_offline_diagnostic_harness_v1.py` to connect the safe
diagnostic contract to the existing PBC08 commit parser using synthetic JSON.
The harness discards parsed commit values and returns only a status, an
allowlisted diagnostic code, and safe key categories. Its PBC05 path normalizes
a supplied synthetic child-process result without launching a process.

Six synthetic integration tests pass. They cover accepted metadata, forbidden
fields, schema failures, unknown parser codes, and sanitized child errors.
The harness performs no file or network I/O and does not connect to an
acquisition executor. Frozen PBC results and the R37 contract snapshot remain
unchanged.

The current suite passes 1185/1185; registry validation passes with 405
analysis registries.

The harness is ready for future offline release-preflight work. Any acquisition
integration still requires a separately versioned executor, tests, and a
scoped release. The exhausted PBC05/PBC08 release cannot be rerun.

Evidence: `registry/analyses/pbc_offline_diagnostic_harness_v1.json`.

Evidence acceptance, acquisition, validation/test access, scoring, and model
training remain closed.
