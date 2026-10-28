# Project Direction Plan R11

Date: 2026-10-28

Exact-48 release V2 executed once. Five snapshots were captured and verified.
Row `020` returned a preserved 4,576-byte HTTP 404 page; 42 rows were not
attempted after the fail-closed stop. This is row-local snapshot unavailability,
not HTTP 429 or transport failure. The original release must not be rerun.

Next: recompute an exact-42 plan excluding captured and quarantined rows, then
freeze V3 tooling that preserves bytes and treats only HTTP 404/410 as row-local
quarantine. HTTP 429, other provider errors and transport errors remain stop conditions.
