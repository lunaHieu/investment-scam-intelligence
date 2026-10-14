# SEC EDGAR/IAPD Wayback availability result V3

## Step name

Execute and independently verify the 70-row unresolved-only V3 retry.

## Meaning

V3 ran after its full 24-hour cooldown and issued exactly one availability
request for each of the 70 rows that was unresolved in V2. Requests were paced
at a minimum of 30 seconds, contacted only the frozen Archive.org availability
endpoint, and never accessed a live candidate domain or downloaded archived
HTML.

The run completed all 70 requests without HTTP 429. Together with the 45
unchanged resolved V2 rows, the cumulative 115-row result contains 42 available
snapshots, 42 unavailable snapshots, and 31 unresolved network errors. The
remaining errors are 15 DNS-resolution failures, 9 connection timeouts, and 7
read timeouts. Twenty-one unresolved rows belong to development and ten to the
external-holdout namespace.

Independent QA reproduced membership, order, parent-row preservation, retry
scope, cooldown compliance, counts, and the closed capture gate. Its status is
`PASS_PARTIAL_ERRORS_PRESERVED_CAPTURE_PLAN_BLOCKED`.

## Decision

Availability is still incomplete, so snapshot capture planning remains closed.
Only a separately frozen V4 release may retry the exact 31 error rows, after at
least another 24-hour cooldown from the V3 report time. Availability does not
create a label or make any record eligible for model use.
