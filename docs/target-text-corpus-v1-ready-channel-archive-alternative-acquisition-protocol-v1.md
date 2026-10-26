# Ready-channel archive alternative acquisition protocol V1

This protocol is an offline-prepared fallback, not permission to bypass the
active 69-row continuation. It activates only if that continuation has a final
report and independent QA confirming an archive-availability endpoint error.

The fallback begins with one metadata-only CDX canary for
`TTCV1_B3_AVAIL_002`, the first never-attempted continuation row. It permits
one request, 60-second pacing, no redirects, a pre-network partial journal,
and no archived-page download. Row `001` remains permanently quarantined and
is never reopened.

The branches are finite:

- Valid HTTP 200 JSON permits preparation of a separate unresolved-only CDX
  metadata release.
- HTTP 429 opens a provider-level circuit and routes the population to a
  non-archive alternative-source assessment.
- Other 4xx responses quarantine the CDX path without blocking the project.
- Invalid content or a parser limitation is reconciled offline from preserved
  bytes; it does not justify another network request.
- An empty result means no eligible CDX snapshot, not a class label.

The canary cannot cascade automatically. Availability or CDX membership never
becomes ground truth, and capture, validation/test access, scoring, and
training remain closed.
