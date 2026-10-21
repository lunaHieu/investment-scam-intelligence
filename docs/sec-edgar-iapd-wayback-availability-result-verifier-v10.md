# SEC EDGAR/IAPD Wayback Availability Result Verifier V10

Date: 2026-10-21
Status: predeclared offline before V10 execution

The verifier independently checks the immutable V10 release and V9 parent,
membership and order, exact two-row retry scope, preservation of all 113
resolved V9 rows, the `not_before` gate, snapshot URL structure, aggregate
counts, HTTP 429 stop behavior and the closed safety contract.

Logical candidate attempts are checked separately from actual HTTP requests.
With `maximum_redirects=3`, actual requests must remain between one and four per
logical attempt.

A partial result preserves both unresolved rows and requires a new separately
frozen cooldown release. A complete result may support a separately declared
supplemental capture amendment later; it never mutates the existing 58-row V5
capture release. This verifier performs no network operations and grants no
capture, label or model permission.
