# SEC/IAPD V11 supplemental capture plan and release

This gate is a separate, hash-bound path for the two rows newly resolved by the
V11 availability retry:

- `TTCV1_EDGAR_AVAIL_HOLDOUT_011` (`murphyllc.com`)
- `TTCV1_EDGAR_AVAIL_HOLDOUT_018` (`wealthmanage.net`)

Both rows remain `EXTERNAL_HOLDOUT`, `UNCERTAIN`, and ineligible for training.
The original 58-row capture plan, 56-row review snapshot, and owner-acceptance
artifacts are immutable and are not enlarged by this release.

## Completed preparation gate

1. The builder recomputed the complete 115-row source/result population from
   the V11 report and selected exactly the two available rows in source order.
2. The independent plan verifier passed with
   `PASS_EXACT_TWO_ROW_SUPPLEMENTAL_CAPTURE_PLAN`.
3. The release builder froze an archive-only execution release with a
   `not_before` exactly 24 hours after the V11 report `created_at`:
   `2026-10-26T05:39:42.463320+07:00`.
4. The independent release verifier passed with
   `PASS_ARCHIVE_ONLY_V11_SUPPLEMENTAL_CAPTURE_RELEASE`.

No archive page was downloaded during this preparation gate. The release is
limited to raw `web.archive.org` replay, one attempt per snapshot, at least 30
seconds between requests, immediate stop on HTTP 429, a partial journal reserved
before network access, no automatic resume, and no overwrite.

## Next permitted gate

At or after the frozen `not_before`, execute the supplemental capture exactly
once only when neither its final report nor partial journal exists. Independently
verify every raw byte/hash. If the capture is complete, create a separate
supplemental exact-text/grouping/review path; never silently merge these rows
into the frozen 56-row snapshot. If it is partial or rate-limited, preserve the
report/journal and prepare a separately justified retry after cooldown.

Text extraction, labeling, validation/test opening, model scoring, and training
remain closed by this release.
