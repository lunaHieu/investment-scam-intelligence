# SEC EDGAR/IAPD Wayback Availability Result V7

Date: 2026-10-19  
Status: independently verified partial result; capture remains blocked

The frozen V7 release executed through the authoritative crash-safe V7
executor at or after its `not_before` gate. Seven of the eight unresolved
candidates were attempted in their frozen order. The seventh attempt received
HTTP 429, so execution stopped immediately and the final candidate was not
contacted, as required.

Independent QA passed with errors preserved:

- 115 total plan rows and original order preserved;
- 107 resolved V6 rows preserved byte-equivalently;
- 58 available, 55 unavailable, and 2 unresolved results;
- seven V7 logical/network requests and 164 cumulative requests;
- two unresolved rows remain in `EXTERNAL_HOLDOUT`;
- no candidate live-domain access, archived-page download, capture, labeling,
  model scoring, validation/test access, or training.

The result does not authorize capture planning. A separate V8 release may
retry only the two unresolved rows after at least 24 hours from
`2026-10-19T14:06:35.423170+07:00`. Capture Tooling V4 supports only a complete
V7 result; a future complete V8 result would require separately frozen and
independently verified V8-aware capture tooling.
