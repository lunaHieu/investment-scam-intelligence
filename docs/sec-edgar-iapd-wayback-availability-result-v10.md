# SEC EDGAR/IAPD Wayback Availability Result V10

Date: 2026-10-22  
Status: independently verified partial result; HTTP 429 preserved

The frozen V10 release ran after its `not_before` gate. The first of the two
quarantined `EXTERNAL_HOLDOUT` candidates returned HTTP 429, so execution
stopped immediately and did not query the second candidate.

Independent QA passed with the partial condition preserved:

- all 115 plan identities and their original order are unchanged;
- all 113 resolved V9 rows remain byte-equivalent;
- 58 rows remain available and 55 remain unavailable;
- two external-holdout rows remain unresolved and quarantined;
- V10 made one logical/network request, bringing the cumulative count to 168;
- the completed 58-row capture plan, 56-row review population, and 42 accepted
  labels were not changed;
- no live candidate domain, archived page, capture, label, model,
  validation/test split, or training operation was opened.

Because V10 stopped on HTTP 429, the independently frozen one-row capture
retry was not executed in this run. Its release remains unchanged. As a
conservative operational cooldown, no further archive request should be made
before `2026-10-23T18:32:45.434853+07:00`. A future availability attempt must
use a new, separately frozen unresolved-only release; V10 must never be rerun.
