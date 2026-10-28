# Reproducibility current state V39

V39 supersedes V38 after successful completion of the ready-channel CDX
canary and independent preparation of the exact unresolved-only bulk release.

The canary made one metadata request for `TTCV1_B3_AVAIL_002`, returned valid
HTTP 200 JSON and two eligible HTML metadata rows, and selected timestamp
`20201029053313`. Raw bytes and metadata recompute under independent QA. The
canary must never be rerun.

The active next release contains exactly `TTCV1_B3_AVAIL_003` through
`TTCV1_B3_AVAIL_070`: 68 rows in original order, including 48 DEVELOPMENT and
20 EXTERNAL_HOLDOUT. It was prepared and verified with zero network requests.
Execution requires a separate invocation, minimum 60-second pacing, one
attempt per row, a non-resumable partial journal and immediate stop on any
error or HTTP 429.

The Crimson readiness state remains 24 tasks ready for truthful human primary
review and 15 official-reference follow-ups. Fresh V1-Core remains 0/300
admitted groups. No capture, label or model gate is open.
