# SEC EDGAR/IAPD Wayback availability result V11

V11 executed the frozen exact-two-row supplemental availability release after its `not_before` gate. It used the archive-availability endpoint only, made one logical attempt per row, waited at least 60 seconds between requests, and did not access candidate live domains or download archived pages.

## Result

- `TTCV1_EDGAR_AVAIL_HOLDOUT_011` and `TTCV1_EDGAR_AVAIL_HOLDOUT_018` were the only retried rows.
- Both requests completed without HTTP 429.
- The final report contains 115 resolved availability rows: 60 available snapshots and 55 unavailable snapshots.
- No unresolved rows remain in the V11 supplemental availability report.
- The original 58-row capture plan, 56-row review, and owner-acceptance snapshot remain unchanged. Any newly available rows require a separately prepared supplemental capture plan.

## Immutable outputs

- Report: `D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_availability_result_v1\availability_report_v11.json`
- Independent QA: `D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_availability_result_v1\independent_qa_v11.json`
- Report SHA-256: `ee1ed9962ab6a0318c3b103989f5303d189949d51e7ab699b4144421a35522bd`
- Independent QA SHA-256: `41cd0806860abce3474450fa401fef3b53a3f553de3d7f64f373d61f545107b`

The result is supplemental availability evidence only. It creates no labels and opens no training, validation, or test gate.
