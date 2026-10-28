# Ready-channel capture-plan release V1

This release builds an offline, all-and-only-eligible raw Wayback capture plan
from the independently verified CDX canary and exact-68 bulk result. Metadata
resolution is complete for rows `002`-`070`, but 16 valid JSON responses have
no eligible snapshot. The exact capture population is therefore 53 records:
37 DEVELOPMENT and 16 EXTERNAL_HOLDOUT. Row `001` remains quarantined and the
16 empty-metadata rows are preserved but not retried or substituted.

Every row pins the selected timestamp, original URL, digest, raw `id_` replay
URL and an unused absolute target beneath the project's raw-data root. The
builder performs no network operation. Independent QA fully recomputes the
plan. This plan does not authorize capture: a separate verified execution
release is required. Candidate live domains, labels, validation/test data,
scoring and training remain closed.
