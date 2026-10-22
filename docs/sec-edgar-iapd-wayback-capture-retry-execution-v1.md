# SEC/IAPD one-row capture retry execution V1

Date: 2026-10-22  
Status: executor and result verifier ready; network gate remains closed

The executor consumes only the frozen one-row release for
`TTCV1_EDGAR_AVAIL_DEV_037`. It verifies the release, independent release QA,
all 57 completed capture byte/hash pairs, and the 23:08 not-before gate before
any request.

A `.partial` journal is created exclusively and flushed before network access.
The executor never resumes a journal, never overwrites a final or partial
report, never follows a redirect outside `web.archive.org`, waits at least 30
seconds per archive request, and makes one logical attempt. Candidate live
domains are never contacted.

For a response below the 1,024-byte minimum, no raw capture is written. The
report retains response byte count, SHA-256, HTTP status, content type, final
archive URL, redirect count, and allowlisted diagnostic headers. HTTP 429 is
recorded and stops the run. A successful raw file is atomically installed and
independently byte/hash verified.

Success opens only a separately versioned supplemental exact-text/grouping/
review path. It cannot alter the frozen 56-row reconciliation. Failure keeps
the row quarantined and does not authorize another retry, a label, model
scoring, validation/test access, or training.
