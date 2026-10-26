# Reproducibility current state V34

B5 has exited the repeated single-row retry loop. Three immutable releases each
made one archive-availability request for `TTCV1_B3_AVAIL_001`; all three
received HTTP 429 without `Retry-After`. The third result QA passes and closes
another identical retry for that row.

The row is quarantined without a label and without blocking the project. The
active release is now Continuation V1: exactly 69 never-attempted rows, 49
`DEVELOPMENT` and 20 `EXTERNAL_HOLDOUT`, in original order from row `002`
through row `070`.

An endpoint-level circuit breaker opens at
`2026-10-26T23:20:12.335732+07:00`, six hours after the third consecutive HTTP
429. The release is independently verified and has its own output path. Earlier
releases and the quarantined request may not be rerun.

Candidate domains, archived page content, labels, validation/test data, model
scoring, and training remain untouched.
