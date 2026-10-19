# SEC EDGAR/IAPD Wayback Availability Result Verifier V8

Date: 2026-10-19  
Status: predeclared offline before V8 execution

The verifier independently checks the immutable V8 release and V7 parent,
membership and order, exact two-row retry scope, byte-equivalent preservation
of all 113 resolved V7 rows, the `not_before` gate, snapshot URL structure,
aggregate counts, HTTP 429 stop behavior, and the closed safety contract.

Logical candidate attempts are verified separately from actual HTTP requests.
With `maximum_redirects=3`, actual requests must be between one and four per
logical attempt; the verifier rejects counts outside that bound.

A partial result keeps every downstream gate closed and requires another
separately frozen cooldown release. A complete result still cannot be consumed
by Capture Tooling V4 because V4 is pinned to a complete V7 result. Separate
V8-aware capture tooling must be frozen and independently verified before any
capture-plan construction.
