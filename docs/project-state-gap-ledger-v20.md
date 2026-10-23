# Project State Gap Ledger V20

Date: 2026-10-23

B2 completed the first materialization step in workstream B. The frozen B1
selection rules produced exactly 70 provenance candidates: 25 development and
10 external-holdout rows in each of the regulator-linked `CONFIRMED` and
IAPD-linked `LEGITIMATE` channels.

Independent recomputation reproduced all 70 identities in the same order.
Candidate IDs, normalized hosts and normalized entities are each 70/70 unique;
development and external holdout have zero host overlap and zero normalized-
entity overlap.

All 70 records remain `UNCERTAIN`. B2 made zero network requests, Wayback
queries, captures, labels, model operations or training admissions. B3 may
prepare a separate frozen Wayback availability release for this exact queue,
but B2 does not authorize its execution. A1/A2 timed archive state and A4's
42-record repair state remain unchanged.
