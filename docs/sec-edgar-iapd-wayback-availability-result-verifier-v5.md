# SEC EDGAR/IAPD Wayback availability result verifier V5

This gate predeclares the independent acceptance rules for the exact V5
unresolved-only retry before any V5 network execution occurs.

The verifier requires the frozen V5 release, the immutable V4 report, and the
immutable independent V4 QA. It independently recomputes row identities,
preserves every V4-resolved outcome, and permits changes only for the exact 23
rows that remained unresolved after V4.

A partial V5 result must retain unresolved rows and keeps capture-plan
preparation closed. Only `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` may open
the next, separately released capture-planning gate. Availability is never a
label, no candidate live domain may be accessed, and this verifier authorizes
no capture, labeling, validation/test access, training, or scoring.
