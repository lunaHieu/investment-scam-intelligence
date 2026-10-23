# Project state and gap ledger V28

V28 replaces V27 after the one-request A1 owner timing override completed and its output was independently recomputed.

- A1 made one archive-metadata request and received a valid canonical empty CDX response (`[]\n`), so no eligible alternate snapshot exists.
- The V1 parser limitation is documented; the immutable execution report remains unchanged and no retry is required.
- The affected development row remains quarantined.
- A2 V11 is frozen for exactly two unresolved external-holdout rows. Its network gate opens at `2026-10-24T21:39:37.725131+07:00`.
- C2 and C3 remain preflight-complete with zero external submissions or human language-review responses.
- V1-Core remains 0/300 fresh admitted groups; 42 owner-accepted records remain conditional and training-ineligible.

No live candidate domain was accessed, no archived page was downloaded, and no label, validation/test, scoring, or training gate was opened.
