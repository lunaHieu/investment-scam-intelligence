# SEC/IAPD Wayback Capture Result V1

Date: 2026-10-21
Status: independently verified partial capture; one row quarantined

## Result

The decoupled crash-safe executor attempted all 58 frozen archive snapshots at
the required minimum 30-second pacing. It contacted only `web.archive.org`,
made 58 network requests, captured 57 immutable HTML files, and encountered no
HTTP 429.

The captured distribution is 45 `DEVELOPMENT` and 12 `EXTERNAL_HOLDOUT` rows.
The 57 files contain 5,473,286 bytes in total; individual sizes range from
1,181 to 601,636 bytes. Independent QA recomputed every membership, order,
file-size and SHA-256 assertion with no errors.

## Quarantined row

`TTCV1_EDGAR_AVAIL_DEV_037` (`lionpoint.com`) returned a 42-byte body from the
frozen raw Wayback replay URL. The body was below the 1,024-byte capture
minimum, so no raw target was written. This proves only that the returned body
was too small; it does not prove that the archived page is absent or unusable.
The original executor did not preserve the rejected body, so its content and
precise cause cannot be reconstructed from local evidence.

## Impact and recovery

The failure affects one `DEVELOPMENT` row. It does not invalidate the 57 files,
the 12-row external-holdout subset, or the two independently quarantined V10
availability rows. No labels, model operations, validation/test access, or
live candidate-domain requests occurred.

Two separately versioned recovery paths are permitted:

1. retry only the missing row with bounded diagnostics and no overwrite; and
2. prepare a 57-row captured-subset admission amendment so independently
   verified rows can proceed to offline exact-text extraction while the failed
   row remains quarantined.

The existing complete-58 exact-text release stays closed. Partial progression
requires a new explicit release and independent QA; it must never disguise the
57-row subset as a complete 58-row capture.

