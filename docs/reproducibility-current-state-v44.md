# Reproducibility current state V44

V44 supersedes V43 after the exact-49 continuation execution and exact-48 V2
preparation.

- Exact-49 result: immutable partial, 0 captured, 1 failed (`010`), 48 not attempted.
- Independent result QA: `PASS_PARTIAL_CONTINUATION_PRESERVED`.
- Quarantines: rows `009` and `010`; neither may be retried identically.
- Exact-48 V2 plan and release: independently verified and immediately open.
- V2 policy: 30-second pacing; one attempt; preserve bytes before classifying;
  continue only after a row-local HTTP 200 content-contract failure; stop on any
  provider HTTP error, HTTP 429, or transport failure.
- Candidate live domains, labels, validation/test, scoring and training remain closed.
