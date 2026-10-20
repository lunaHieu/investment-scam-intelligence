# SEC EDGAR/IAPD Partial-Resolved Capture Amendment V1

Date: 2026-10-20
Status: frozen offline amendment; no capture performed

This amendment removes the two unresolved V8 availability rows from the
critical path without interpreting either error. It authorizes planning only
for every V8 row with `available=true` and valid snapshot evidence.

The builder and independent verifier must recompute all 115 source/result rows,
preserve original order and cohort identity, select all 58 resolved available
rows, exclude all 55 resolved unavailable rows, and quarantine the exact two
unresolved `EXTERNAL_HOLDOUT` identities in their frozen order. The unresolved
rows remain eligible for V9 and any later supplemental release.

The resulting corpus must be described as an `archive-available subset`, not a
representative external holdout. Availability, exclusion, and registry identity
are not labels. No candidate live domain is accessed.

Capture Tooling V5 is specific to the independently verified V8 partial result.
Its release remains archive-only, uses raw Wayback replay, waits at least 30
seconds between requests, stops immediately on HTTP 429, never replaces failed
rows, and refuses overwrite. A concrete release still requires a 24-hour gate
anchored to the V8 report creation time.
