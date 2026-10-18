# SEC EDGAR/IAPD Wayback Availability Result V6

Date: 2026-10-18  
Status: independently verified partial result; capture remains blocked

The frozen V6 release executed through the authoritative crash-safe V6.1
executor at or after its `not_before` gate. The first and only V6 request
received HTTP 429, so execution stopped immediately as required. No later
candidate was contacted.

Independent QA passed with errors preserved:

- 115 total plan rows and original order preserved;
- 107 resolved V5 rows preserved byte-equivalently;
- 52 available, 55 unavailable, and 8 unresolved results;
- one V6 network request and 157 cumulative requests;
- four unresolved rows remain in `EXTERNAL_HOLDOUT`;
- no candidate live-domain access, archived-page download, capture, labeling,
  model scoring, validation/test access, or training.

The result does not authorize capture planning. A separate V7 release may
retry only the same eight unresolved rows after at least 24 hours from
`2026-10-18T09:45:26.642053+07:00`. Even a complete V7 result cannot be passed
to Capture Tooling V3, which supports only availability generations V3–V6;
separate V7-aware capture tooling must be frozen and independently verified.
