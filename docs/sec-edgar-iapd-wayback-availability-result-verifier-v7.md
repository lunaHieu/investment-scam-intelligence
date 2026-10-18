# SEC EDGAR/IAPD Wayback Availability Result Verifier V7

Date: 2026-10-18  
Status: predeclared offline before V7 execution

The verifier independently checks the immutable V7 release and V6 parent,
membership and order, exact eight-row retry scope, byte-equivalent preservation
of all 107 resolved V6 rows, the `not_before` gate, snapshot URL structure,
aggregate counts, HTTP 429 stop behavior, and the closed safety contract.

Logical candidate attempts are verified separately from actual HTTP requests.
With `maximum_redirects=3`, actual requests must be between one and four per
logical attempt; the verifier rejects counts outside that bound.

A partial result keeps every downstream gate closed and requires another
separately frozen cooldown release. A complete result still cannot be consumed
by Capture Tooling V3 because V3 supports only availability V3–V6. Separate
V7-aware capture tooling must be frozen and independently verified before any
capture-plan construction.
