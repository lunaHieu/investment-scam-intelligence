# Reproducibility current state V33

V33 records B5 after the first adaptive retry. The original exact-70 release
and retry V2 are immutable and must not be rerun. Each made one request for
`TTCV1_B3_AVAIL_001`; each received HTTP 429 without `Retry-After`; each
finalized a 70-row report with no partial journal. Independent result QA passes
for both reports.

The active release is retry V3. It retains the original 70 ordered identities,
50 `DEVELOPMENT` and 20 `EXTERNAL_HOLDOUT`, and opens at
`2026-10-26T10:49:40.978852+07:00`. This one-hour gate is the second step of
the bounded adaptive schedule, not a universal 24-hour cooldown.

V3 is the third and final identical attempt for the triggering row. If it
again receives HTTP 429, the triggering row cannot be retried identically. It
will be quarantined and remaining independent work will be split out, so the
project cannot remain in an endless retry loop.

No candidate live domain or archived page content has been accessed in B5.
Capture planning, labeling, validation/test opening, model scoring, and
training remain closed.
