# Project Direction Plan R8

Date: 2026-10-28

R8 records the immutable partial ready-channel capture result.

## Verified outcome

- Original exact-53 release: consumed and must not be rerun.
- Network requests: 4; captured and hash-verified: 3 DEVELOPMENT rows.
- Failure: row `009`, valid archive response of 870 bytes below the frozen
  1,024-byte minimum; not HTTP 429 and not a transport failure.
- Not attempted after fail-closed stop: 49 rows.
- Exact-text extraction remains closed.
- Current suite target: 1029 tests; registry target after navigation: 277.

## Next order

1. Prepare and verify a separate continuation for only the 49 never-attempted
   rows, excluding the three captured rows and row `009`; no fixed 24-hour
   delay is required.
2. Independently design response-preserving diagnostics for row `009`; do not
   issue an identical retry or silently lower the minimum.
3. Execute the 49-row continuation in a later invocation and QA every byte.

No label, validation/test, scoring or training gate is open.
