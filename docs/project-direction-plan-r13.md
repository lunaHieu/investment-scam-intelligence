# Project Direction Plan R13

Date: 2026-10-28

The exact-42 V3 release and independent QA are complete. Execution is open
without a fixed cooldown. HTTP 404/410 responses are preserved and quarantined
per row; HTTP 429, 5xx, transport errors and unclassified provider failures
remain fail-closed. Next: execute V3 once, verify every capture/diagnostic byte,
then reconcile the complete usable population only if result QA permits it.
