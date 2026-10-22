# SEC EDGAR/IAPD One-Row Capture Retry Result V1

Date: 2026-10-22  
Status: retry failed deterministically; quarantine remains

The project owner explicitly waived the additional operational cooldown on
2026-10-22. The underlying frozen release's original `not_before`
(`2026-10-22T23:08:09.711801+07:00`) had already opened, so no frozen release,
hash, identity, or no-overwrite rule was changed.

The policy-compliant V2 executor made exactly one raw Wayback replay request
for `TTCV1_EDGAR_AVAIL_DEV_037`. Internet Archive returned HTTP 200 with
`text/html; charset=UTF-8`, but the body was again exactly 42 bytes. Its SHA-256
is `1c98e3ca60f14fecc235ee47c09ec2fd61f4b3a696251174c4723024279d95e3`.
No HTTP 429 occurred, and no raw capture file was written.

This repeat of the original 42-byte result shows that the failure belongs to
the selected archived replay, not to the earlier availability rate limit. The
row remains quarantined and cannot enter exact-text extraction, grouping,
review, labeling, scoring, or training.

The historical V1 result verifier exposed a separate post-execution design
bug: it reused a pre-execution validator that requires the planned report to
be absent, so it necessarily failed after the report existed. That failed QA
artifact is preserved. The versioned V2 verifier independently checks the
frozen release and QA hashes, all 57 completed captures, the final report,
response diagnostics, and raw-file absence. V2 QA passed with
`PASS_RETRY_FAILURE_PRESERVED_QUARANTINE_REMAINS`.

Another retry is not authorized by this result. The technically justified
next option is a separately frozen CDX enumeration of alternate snapshots for
this one row; repeatedly requesting the same timestamp is not useful.
