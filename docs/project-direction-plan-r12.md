# Project Direction Plan R12

Date: 2026-10-28

The exact-42 V3 continuation plan passed independent full recomputation. It
contains only rows never attempted after V2, excludes all eight immutable
captures and rows `009`, `010`, `020`, and preserves original order/cohorts.

Next: build and independently verify V3 release tooling. It may quarantine
preserved HTTP 404/410 responses per row, but must stop on HTTP 429, 5xx,
transport errors, or any unclassified provider failure. No network execution is
authorized until that separate release passes QA.
