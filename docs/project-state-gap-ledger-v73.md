# Project State Gap Ledger V73

## PBC parser-bound diagnostic follow-up

The exact-two-row PBC result is preserved. Offline synthetic checks narrowed
the failure boundary without accessing a source endpoint:

- PBC05's child returned 1 with no stdout, whereas the extractor's handled
  exception path prints a bounded JSON code and exits 2. This is inconsistent
  with an ordinary handled extraction exception. Exact cause is still
  unrecoverable because stderr text and the PDF were not retained.
- PBC08 accepts the synthetic allowlisted commit schema and drops extra
  non-forbidden fields. The configured forbidden-key scan rejects matches at
  any nesting level, without retaining values or names. The exact live key is
  unknown.

The synthetic suite passed 5/5. No network request, candidate access, dataset
row, label, validation/test access, or model operation occurred. Same-release
retry remains forbidden; no new source request is authorized. The detailed
hash-pinned record is `registry/analyses/target_text_corpus_v1_pbc_offline_followup_v1.json`.

Do not treat availability, metadata, or these parser diagnostics as label
evidence. Evidence acceptance and training remain closed.
