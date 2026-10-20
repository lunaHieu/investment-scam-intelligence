# SEC EDGAR/IAPD Wayback Availability Result V8

Date: 2026-10-20  
Status: independently verified partial result; capture remains blocked

The frozen V8 release executed through the authoritative crash-safe V8
executor at or after its `not_before` gate. Both unresolved candidates were
attempted in their frozen order. The first request failed at DNS resolution;
the second received HTTP 429, so execution stopped immediately as required.

Independent QA passed with errors preserved:

- 115 total plan rows and original order preserved;
- 113 resolved V7 rows preserved byte-equivalently;
- 58 available, 55 unavailable, and 2 unresolved results;
- two V8 logical/network requests and 166 cumulative requests;
- two unresolved rows remain in `EXTERNAL_HOLDOUT`;
- no candidate live-domain access, archived-page download, capture, labeling,
  model scoring, validation/test access, or training.

The result does not authorize capture planning. A separate V9 release may
retry only the two unresolved rows after at least 24 hours from
`2026-10-20T14:19:54.213531+07:00`. Capture Tooling V4 supports only a complete
V7 result; a future complete V9 result would require separately frozen and
independently verified V9-aware capture tooling.
