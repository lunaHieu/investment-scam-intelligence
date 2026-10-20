# SEC EDGAR/IAPD Partial-Resolved Capture Plan and Release V5

Date: 2026-10-20
Status: frozen and independently verified; waiting for capture not-before

The V5 protocol amendment consumes the immutable V8 availability result without
claiming that availability is complete. It recomputes all 115 candidates,
selects all and only the 58 rows with `available=true` in original order, and
quarantines the two unresolved `EXTERNAL_HOLDOUT` rows without labels.

The frozen capture plan contains 46 `DEVELOPMENT` and 12 `EXTERNAL_HOLDOUT`
snapshots. The holdout subset is an archive-available subset and must not be
reported as representative of the full external population.

The independently verified execution release may run at or after
`2026-10-21T14:19:54.213531+07:00`. It permits only raw Wayback replay from
`web.archive.org`, at least 30 seconds between requests, one attempt per
snapshot, immediate stop on HTTP 429, and no overwrite. No live candidate
domain access, text extraction, labeling, validation/test access, scoring, or
training is authorized by this release.

The separate V9 availability retry remains responsible for only the two
quarantined rows. Its outcome cannot silently alter this 58-row release.
