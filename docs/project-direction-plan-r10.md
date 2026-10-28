# Project Direction Plan R10

Date: 2026-10-28

The exact-49 continuation executed once and stopped safely on its first row.
Row `010` returned an HTTP body of 114 bytes, below the 1,024-byte capture
minimum. There was no HTTP 429 or transport failure. Because the V1 executor
did not preserve below-minimum bytes, the response meaning cannot be recovered
offline and identical retry is not authorized.

The project is not blocked. An independently recomputed exact-48 plan excludes
rows `009` and `010`, preserves order/cohorts, and passed QA. Release V2 is open
without a fixed 24-hour delay. Its executor preserves every response body and
continues after verified row-local content errors, while provider/transport
errors remain fail-closed.

Next: execute exact-48 release V2 in a separate invocation, independently verify
all capture and diagnostic bytes, then reconcile the usable captured subset.
