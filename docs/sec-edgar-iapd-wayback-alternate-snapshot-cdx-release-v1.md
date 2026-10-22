# SEC/IAPD Alternate-Snapshot CDX Release V1

Date: 2026-10-22  
Status: frozen offline preparation; network gate closed

## Step name and meaning

This is plan step A1. It freezes an archive-metadata-only CDX enumeration for
the single quarantined development row `TTCV1_EDGAR_AVAIL_DEV_037`. Its purpose
is to identify a different Wayback timestamp without repeating the replay that
twice returned the same 42-byte body.

The release does not contact `lionpoint.com`, download archived page content,
create a raw artifact, inspect content for selection, infer a label, mutate the
completed 56-row review snapshot, score a model, or train a model.

## Frozen identity and exclusion

- Candidate host: `lionpoint.com`.
- Cohort: `DEVELOPMENT`.
- Failed timestamp: `20260210193325`.
- Failed response bytes: 42.
- Failed response SHA-256:
  `1c98e3ca60f14fecc235ee47c09ec2fd61f4b3a696251174c4723024279d95e3`.
- The failed timestamp is explicitly excluded both in the CDX request filter
  and again during offline response parsing.

## CDX contract

The only permitted endpoint is
`https://web.archive.org/cdx/search/cdx`. The execution budget is one logical
request and one attempt. Pacing is at least 60 seconds, redirects are not
followed, HTTP 429 stops immediately, and diagnostic headers are preserved.
A partial journal must exist before the request and may never be automatically
resumed or overwritten.

The exact CDX field order is:

1. `timestamp`
2. `original`
3. `statuscode`
4. `mimetype`
5. `digest`

Eligible rows must have a 14-digit non-excluded timestamp, canonical host
`lionpoint.com`, canonical path `/`, status 200, MIME type `text/html`, and a
32-character Base32 SHA-1 digest. The deterministic selection order is minimum
absolute time distance from the failed timestamp, then earlier timestamp, then
original URL, then digest. Page content and label information are forbidden
selection inputs.

## Time and downstream gates

The prior archive request was created at
`2026-10-22T23:35:43.595958+07:00`. Therefore this release cannot make its one
CDX request before `2026-10-23T23:35:43.595958+07:00`. The one-time owner
override used for the prior retry is recorded as consumed and is not inferred
for this release.

Even if an alternate metadata row is selected, this release does not authorize
capture. A separately frozen capture release and independent QA are mandatory.
Any successful artifact must follow a supplemental exact-text, grouping,
review, reconciliation, and owner-acceptance path; it cannot be inserted into
the frozen 56-row population.

## Offline verification result

Independent release QA status is
`PASS_FROZEN_ONE_ROW_ARCHIVE_METADATA_ONLY_CDX_RELEASE`. Preparation performed
zero network operations, zero candidate-domain accesses, zero archived-page
downloads, zero raw writes, zero labels, and zero model operations.
