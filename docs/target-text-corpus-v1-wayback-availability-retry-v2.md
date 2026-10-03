# Target Text Corpus V1 Wayback availability retry V2

The first availability run stopped exactly as required after Wayback returned HTTP 429 on request 10. Its immutable report records five available snapshots, four resolved unavailable results, the rate-limit error, and thirty candidates that were deliberately not queried.

V2 retries only those 31 unresolved rows. The nine resolved V1 rows are copied unchanged into the combined V2 report and never requested again. The retry uses one attempt per unresolved candidate and a six-second minimum delay, equivalent to no more than roughly one request per six seconds. A second HTTP 429 again stops the remaining requests and preserves them as unresolved.

The retry is still availability-only: it accesses only `archive.org` or `web.archive.org`, downloads no archived HTML, never opens a candidate domain, never creates a label, and refuses to overwrite an existing report. Capture planning remains blocked unless all 40 combined results are resolved.
