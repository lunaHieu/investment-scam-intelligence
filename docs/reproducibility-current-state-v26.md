# Reproducibility current state V26

V26 supersedes V25 after V11 completed the exact-two-row supplemental availability retry. The result is independently verified and remains separate from the frozen 58-row capture/review snapshot.

## Current state

- Availability: 115 total rows resolved; 60 available and 55 unavailable.
- V11: two requests, no HTTP 429, no unresolved rows.
- Original capture plan: unchanged; newly available rows require a separate supplemental capture plan.
- Owner acceptance: 42 `LEGITIMATE`, 14 `UNCERTAIN`; training eligibility remains zero.

## Reproduction command

From the repository root:

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_wayback_availability_result_v11 --release configs/sec_edgar_iapd_wayback_availability_release_v11.json --release-qa D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_availability_result_v1\independent_release_qa_v1.json --report D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_availability_result_v1\availability_report_v11.json --output D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_all_filer_wayback_availability_result_v1\independent_qa_v11.json
```

No labels, archived-page captures, validation/test openings, or model operations are authorized by this state.
