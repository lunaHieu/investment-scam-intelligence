# SEC EDGAR/IAPD Wayback Availability Result V5

Date: 2026-10-17  
Status: independently verified partial result; capture planning blocked

The frozen V5 release retried exactly the 23 rows that remained unresolved after V4. It issued 23 archive-availability requests at the committed minimum 60-second spacing and did not encounter HTTP 429.

Independent QA verified that membership and order were preserved, all 92 resolved V4 rows remained unchanged, only prior unresolved rows were queried, and the cooldown gate was respected.

The cumulative result contains 107 resolved rows: 52 archive-available and 55 unavailable. Eight rows remain unresolved because of network timeout or DNS errors, including four EXTERNAL_HOLDOUT rows. Errors remain errors and are not interpreted as unavailable snapshots.

Capture planning remains closed. A separately frozen V6 release may retry only those eight unresolved rows no earlier than 24 hours after the V5 report creation time. Availability is neither captured content nor label evidence.

No candidate live domain, archived page, model, validation set, or test set was accessed by this workflow.
