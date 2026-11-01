# Project State Gap Ledger V74

## Offline parser-diagnostic readiness

An isolated diagnostic helper is prepared for a future, separately scoped
parser version. It maps forbidden JSON keys to fixed categories and reports
only allowlisted child exception classes and stages. Raw key names, paths,
values, stdout, and stderr are never returned. Parsing limits are 64 KiB for
stdout JSON and 4 KiB for the stderr tail used to identify an exception class.

The helper has eight synthetic tests; the current full suite passes 1177/1177,
and registry validation passes with 402 analysis registries. It is not wired to the current executor,
does not authorize source requests, and does not alter immutable PBC results.
PBC05's exact child cause and PBC08's exact offending key remain unknown. The
old release stays exhausted; no new release has been prepared.

No data rows or labels were admitted. Validation/test, scoring, and training
gates remain closed. Detailed evidence is in
`registry/analyses/pbc_safe_diagnostic_contract_v1.json`.
