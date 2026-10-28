# Project Direction Plan R5

Date: 2026-10-28

R5 incorporates the unchanged R2-R4 scope and records the finite successful
CDX canary transition.

## Verified amendment

- The one-row canary executed exactly once and returned valid HTTP 200 JSON.
- Raw 286-byte response and metadata were independently verified.
- Row 002 is resolved with two eligible metadata rows; row 001 remains
  quarantined.
- A separate exact unresolved-only release is frozen for rows 003-070: 68
  records, 48 DEVELOPMENT and 20 EXTERNAL_HOLDOUT.
- Bulk execution did not occur in the canary/preparation run.
- No candidate live domain or archived page was opened; no label was created.
- Current suite: 1015 tests passed under lifecycle-aware V2; current registry:
  265 analysis registries validated.

## Next executable order

1. In a separate invocation, execute the exact-68 CDX metadata release once
   with at least 60-second pacing and stop on the first error or HTTP 429.
2. Independently verify every preserved raw response and parsed metadata row.
3. Prepare a capture plan only after complete CDX result QA; partial results
   remain non-resumable and require a separately justified branch.
4. Continue the independent Crimson and exact-42 human-review workstreams.

Capture, labeling, validation/test, scoring and training remain closed.
