# Ready-channel CDX metadata canary release V1

The exact-69 availability continuation executed once and stopped fail-closed on
its first request after HTTP 429. Independent QA preserved all 69 rows as
unresolved and kept capture, labeling and training closed.

The finite fallback therefore activates only a one-row metadata canary for
`TTCV1_B3_AVAIL_002`. It queries the Internet Archive CDX metadata endpoint,
never the candidate live domain, and never downloads an archived page. The
release permits one request, one attempt, no redirects, a pre-network partial
journal and no overwrite.

The fourth consecutive provider rate-limit event has no valid `Retry-After`
header. The frozen adaptive retry policy therefore selects its fourth bounded
delay of 86,400 seconds. The canary cannot run before
`2026-10-28T09:32:33.798697+07:00`.

The branch is finite:

- valid JSON, including canonical empty JSON, permits preparation of a separate
  unresolved-only CDX metadata release;
- HTTP 429 closes the archive-provider branch and routes the population to
  non-archive source assessment;
- invalid content preserves response bytes for offline reconciliation;
- other errors quarantine the CDX path without blocking independent project
  work.

The canary never creates a label and cannot automatically cascade into bulk
enumeration, capture, validation/test access, scoring or training.
