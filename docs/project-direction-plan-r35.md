# Project Direction Plan R35

The separately authorized diagnostic execution covered exactly PBC05 and
PBC08 and is complete. Both endpoints returned HTTP 200, but both resources
were parser-rejected.

PBC05 returned the same PDF bytes as before and again failed at
`SECTION_EXTRACTION`; the instrumented child process produced no structured
diagnostic on stdout, so the exact failure remains unresolved. Do not retry
PBC05 under the same release.

PBC08 is now localized to the `FORBIDDEN_DATASET_KEY_PRESENT` guard. The
offending key was not retained, so do not infer which key caused rejection.
Do not retry PBC08 under the same release.

The two-row result and QA are registered. No raw response, dataset file, row,
label or model output was retained. The finite diagnostic release is closed;
any further acquisition requires a new technical rationale and separately
scoped authorization. All data-use and model gates remain closed.
