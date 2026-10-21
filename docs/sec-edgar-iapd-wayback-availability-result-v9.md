# SEC EDGAR/IAPD Wayback Availability Result V9

Date: 2026-10-21
Status: independently verified partial result; V5 capture preserved but deferred

The frozen V9 release ran after its `not_before` gate. The first unresolved
candidate received HTTP 429, so execution stopped immediately before the
second candidate, exactly as required by the release contract.

Independent QA passed with errors preserved:

- all 115 plan identities and their original order are unchanged;
- all 113 resolved V8 rows remain preserved;
- 58 rows remain available and 55 remain unavailable;
- two `EXTERNAL_HOLDOUT` rows remain unresolved and quarantined;
- V9 made one logical/network request, bringing the cumulative count to 167;
- no candidate live-domain access, archived-page download, capture, label,
  model operation, validation/test access, or training occurred.

The separately frozen 58-row V5 capture release is not invalidated or enlarged
by this result. Because V9 stopped on HTTP 429, the same execution run did not
start capture. A new exact two-row V10 availability retry must observe at least
24 hours from `2026-10-21T18:18:58.983066+07:00`. Capture remains independently
authorized by its unchanged V5 release, but is conservatively deferred to the
next scheduled run so it does not immediately follow a rate limit.
