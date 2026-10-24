# Reproducibility current state V27

V27 supersedes V26 after the V11 supplemental capture plan and release were
independently verified. The two newly available holdout rows are kept on a
separate path; the frozen 58-row capture/review snapshot is unchanged.

## Current state

- Availability: 115 total rows resolved; 60 available and 55 unavailable.
- V11: two requests, no HTTP 429, no unresolved rows.
- Supplemental plan: exactly two `EXTERNAL_HOLDOUT` rows in source order.
- Supplemental plan QA: `PASS_EXACT_TWO_ROW_SUPPLEMENTAL_CAPTURE_PLAN`.
- Supplemental release QA: `PASS_ARCHIVE_ONLY_V11_SUPPLEMENTAL_CAPTURE_RELEASE`.
- Supplemental capture `not_before`: `2026-10-26T05:39:42.463320+07:00`.
- Owner acceptance: 42 `LEGITIMATE`, 14 `UNCERTAIN`; training eligibility remains zero.

## Reproduction commands

From the repository root:

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_v11_supplemental_capture_plan --plan D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_plan_v1\capture_plan_v1.json --plan-sha256 3bab858b4c9a03ee5544981c64b4082b4dafa4440ba25293b2b65dad42f65286 --output D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_plan_v1\independent_qa_v1.json
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_v11_supplemental_capture_release --release configs/sec_edgar_iapd_v11_supplemental_capture_release_v1.json --output D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_plan_v1\independent_release_qa_v1.json
```

No archive-page capture, text extraction, labels, validation/test openings, or
model operations are authorized before the supplemental release gate.
