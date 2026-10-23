# Project State Gap Ledger V22

Date: 2026-10-23

B4 froze and independently verified the crash-safe executor for the exact 70
rows prepared by B3. The execution population is unchanged: 50 development
and 20 external-holdout candidates, with the original order and all prior
disjointness guarantees preserved.

The executor reserves a non-resumable partial journal before any network
access, waits at least 60 seconds before every request including redirects,
allows one logical attempt per candidate, preserves rate-limit diagnostics,
and stops on HTTP 429 or any transport, HTTP, or parsing failure. It contacts
only the Internet Archive availability service and never a candidate domain.

B4 made zero network requests. Its immutable release QA passed, but B5 remains
closed until A1 has a successful independently verified final result and both
time conditions have passed: the absolute floor
`2026-10-25T00:00:00+07:00` and 24 hours after A1's actual report
`created_at`. An absent, partial, failed, or rate-limited A1 result keeps B5
closed. A1/A2, A4, capture, labeling, validation/test, scoring, and training
states remain unchanged.
