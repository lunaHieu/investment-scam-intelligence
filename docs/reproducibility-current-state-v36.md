# Reproducibility current state V36

The exact-69 B5 continuation is complete as an immutable partial execution and
must never be rerun. It made one request for `TTCV1_B3_AVAIL_002`, received
HTTP 429, stopped fail-closed and preserved all 69 rows as unresolved.
Independent QA passed with capture-plan preparation closed.

Row `TTCV1_B3_AVAIL_001` remains quarantined after three earlier identical
availability attempts. The active next release is the separately frozen
one-row CDX metadata canary for `TTCV1_B3_AVAIL_002`. Its adaptive gate opens at
`2026-10-28T09:32:33.798697+07:00` after the fourth bounded provider rate-limit
step. The release permits exactly one metadata request, no redirects, no live
candidate-domain access and no archived-page download.

The canary is terminal for provider diagnosis. Valid JSON may lead only to a
separately frozen unresolved-only metadata release. HTTP 429 closes the archive
provider branch and routes the remaining population to non-archive source
assessment. Invalid content is reconciled offline from preserved response
bytes. No branch automatically cascades.

Project Direction Plan R2 is the current planning guide. It does not change
frozen cohort identities or open capture, labeling, validation/test, scoring or
training. The fresh corpus remains 0/300 admitted groups; 42 owner-accepted
records remain conditional supply pending complete admission fields.
