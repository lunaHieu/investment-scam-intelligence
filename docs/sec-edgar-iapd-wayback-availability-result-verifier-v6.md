# SEC EDGAR/IAPD Wayback Availability Result Verifier V6

Date: 2026-10-17  
Status: predeclared before V6 result creation

The verifier independently recomputes V6 membership, ordering, parent-row preservation, retry scope, aggregate counts, cooldown compliance, snapshot URL validity, error preservation, HTTP 429 behavior, and the closed safety contract.

Only `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` may allow preparation of a separate capture plan. A partial pass keeps capture planning closed and requires another separately declared cooldown release. The verifier performs no network access and cannot create labels or open model data.
