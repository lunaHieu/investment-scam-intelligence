# SEC EDGAR/IAPD Wayback availability retry V5

V5 preserves all 92 resolved V4 rows and may retry only the 23 unresolved rows.
It cannot execute before `2026-10-17T01:19:27.607186+07:00`, exactly 24 hours
after the V4 report. Because V4 stopped on HTTP 429, V5 slows pacing from 30 to
60 seconds per request, keeps one attempt per row and stops immediately on a
new 429.

This is archive availability only. It does not download archived pages, access
candidate domains, create artifacts or labels, open validation/test, or run a
model. A future V5 result must pass the predeclared independent verifier; only
zero unresolved rows may permit preparation of a separate capture plan.
