# Ready-channel capture continuation plan V2

This plan is an immutable, exact recomputation of the 48 rows that were not attempted after the V1 continuation stopped on row `TTCV1_B3_AVAIL_010`.

- Three earlier captures remain immutable.
- Rows `TTCV1_B3_AVAIL_009` and `TTCV1_B3_AVAIL_010` are quarantined and excluded.
- Original order and DEVELOPMENT/EXTERNAL_HOLDOUT identities are preserved.
- No candidate live domain is accessed, and no label or model operation is authorized.

The V2 execution policy may continue after a verified row-local short HTTP 200 response only when the raw response bytes and diagnostics are preserved. Provider errors, HTTP 429, and transport errors remain fail-closed.
