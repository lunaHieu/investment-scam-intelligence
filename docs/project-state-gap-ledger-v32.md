# Project state gap ledger V32

V32 records the metadata-limited offline repair of the V11 supplemental
capture. Historical V5 capture, 56-row review, owner acceptance, and model
gates remain immutable.

## Completed evidence

- The preserved reservation, raw-byte reconciliation, and repaired report are
  all hash-bound without overwrite.
- Repaired report contains exactly the two planned rows in source order and
  recomputes both local raw SHA-256 hashes.
- Independent repaired QA passed with
  `PASS_REPAIRED_RAW_BYTES_METADATA_INCOMPLETE_EXTRACTION_CLOSED`.
- No network operation, label creation, validation/test opening, or model
  operation occurred during repair.

## Still closed

Strict capture QA, exact-text extraction, grouping, labeling,
validation/test opening, model scoring, and training remain closed. The repair
does not fabricate HTTP status, content type, redirect count, or request
diagnostics and cannot enlarge the original 58/56-row snapshot.

## Next gate

Treat the two rows as supplemental raw-byte evidence only. Reopening exact-text
processing requires a separately justified archive release that persists full
response metadata; do not recapture or merge implicitly.
