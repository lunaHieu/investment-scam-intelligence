# PBC05/PBC08 Offline Postmortem and PBC06/PBC07 Registration V1

PBC05 is confirmed to fail in the section-extraction subprocess with return
code 1. The exact exception is not recoverable because stderr text and the raw
PDF were intentionally discarded. PDF parsing/page extraction, the page-limit
guard and a runtime error remain bounded hypotheses rather than conclusions.

PBC08 is confirmed only as a parser `ValueError`. Static parser review shows
four possible guards: a forbidden dataset-like key, no commit list at the root
or `commits` field, a non-object commit entry, or a commit ID that is not 40
hexadecimal characters.
No one guard is promoted to fact without the discarded response.

PBC06 repository metadata and PBC07 bounded documentation metadata are
registered by response hash and revision identity. This registration records
provenance only. It authorizes no dataset download, admits zero rows, creates
zero labels and does not open validation, model or training gates.
