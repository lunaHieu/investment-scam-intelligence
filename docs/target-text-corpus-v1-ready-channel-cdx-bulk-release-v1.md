# Ready-channel CDX bulk release V1

The canary returned valid JSON and two eligible metadata rows for
`TTCV1_B3_AVAIL_002`. This release therefore freezes the remaining exact
unresolved-only population: `TTCV1_B3_AVAIL_003` through
`TTCV1_B3_AVAIL_070`, preserving original order and cohorts.

Rows 001 and 002 are excluded for different binding reasons: row 001 is the
permanent identical-request quarantine, while row 002 is the resolved canary.
The release covers 68 rows: 48 DEVELOPMENT and 20 EXTERNAL_HOLDOUT; 33
regulator-linked `CONFIRMED` candidates and 35 IAPD-linked `LEGITIMATE`
candidates.

Execution must be a separate invocation. It uses metadata-only CDX queries,
minimum 60-second pacing, one attempt per row, a crash-safe non-resumable
partial journal, raw-response preservation and immediate stop on HTTP 429 or
any transport/HTTP error. It never opens candidate domains or downloads
archived pages. Preparation creates no label and opens no model gate.
