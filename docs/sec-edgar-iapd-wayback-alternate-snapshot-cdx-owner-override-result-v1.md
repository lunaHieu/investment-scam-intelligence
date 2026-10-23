# SEC/IAPD alternate-snapshot CDX owner-override result V1

A1 was executed exactly once under the project owner's explicit timing-only exception. The request retained the frozen 60-second pacing, one-request maximum, archive-metadata-only scope, stop-on-429, no-overwrite, and no-live-domain rules.

The CDX endpoint returned HTTP 200, `application/json`, and the exact three-byte body `[]\n`. Its SHA-256 is `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`. This is a valid zero-row CDX response: no eligible alternate snapshot exists for the frozen query.

The V1 executor preserved the response as `INCOMPLETE_ERROR_PRESERVED` because its parser required a non-empty table header. Independent V2 recomputation classifies the cause as a parser limitation, not a network failure or rate limit. The immutable V1 report is not changed.

Decision: A1 is complete, the same query must not be retried, no supplemental capture release may be prepared, and `TTCV1_EDGAR_AVAIL_DEV_037` remains quarantined. No archived page was downloaded, no candidate live domain was contacted, and no label or model state changed.
