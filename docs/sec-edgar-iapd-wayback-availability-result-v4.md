# SEC EDGAR/IAPD availability result V4

V4 ran once after its cooldown and stopped immediately on HTTP 429 after ten
archive-availability requests. Independent QA verified the full 115-row order,
preservation of all prior resolved rows, unresolved-only retry membership and
the zero-capture safety contract.

The cumulative result contains 45 available, 47 unavailable and 23 unresolved
rows. Capture-plan construction remains blocked. V4 is consumed and must never
be rerun. A separately frozen V5 may contain only those 23 unresolved rows and
must not execute before `2026-10-17T01:19:27.607186+07:00`.
