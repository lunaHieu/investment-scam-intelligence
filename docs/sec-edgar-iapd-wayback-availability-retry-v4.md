# SEC EDGAR/IAPD Wayback availability retry V4

## Step name

Freeze a 24-hour cooldown release for the 31 unresolved archive-availability rows.

## Meaning

V3 resolved 39 of its 70 retried rows and left 31 network errors. V4 preserves
all 84 resolved objects in the 115-row report unchanged and may query only those
31 error rows. The release cannot execute before **2026-10-16 00:48:55 +07:00**,
exactly 24 hours after the V3 report time. It permits at most one request per
unresolved row with at least 30 seconds between requests.

This remains an availability check, not page capture. The executor is restricted
to `archive.org` and `web.archive.org`, stops immediately on HTTP 429, preserves
network errors as unresolved, and refuses to overwrite an existing result.

## Current decision

The release and its independent offline QA are frozen. Network execution is
still closed until the `not_before` time. No request was sent while preparing
this release. Live candidate domains, archived HTML download, artifact capture,
labeling, model operations, and validation/test opening remain blocked.

Only a complete 115-row resolved report may allow preparation of a separate
snapshot-selection and capture plan.
