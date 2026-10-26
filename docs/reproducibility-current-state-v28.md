# Reproducibility current state V28

V28 supersedes V27 after the V11 supplemental archive-only execution. The
executor reported two successful raw captures, but its final report was not
persisted and remained the pre-network reservation. That reservation and the
independent verifier failure are immutable; no recapture is authorized.

## Current state

- Availability: 115 total rows resolved; 60 available and 55 unavailable.
- Frozen original snapshot: 58-row capture, 56-row review, and owner acceptance
  remain unchanged (42 `LEGITIMATE`, 14 `UNCERTAIN`, training eligibility zero).
- Supplemental plan: exactly two `EXTERNAL_HOLDOUT` rows, in source order.
- Raw files: both supplemental files are present and hash-recorded offline.
- Capture QA: `FAIL` because the persisted report is still the reservation and
  does not contain the executor's result rows/metadata.
- Raw-byte reconciliation: `PASS_RAW_BYTES_IDENTITY_RECONCILIATION_CAPTURE_METADATA_INCOMPLETE`.

## Boundaries

The reservation, failed QA, and raw-byte reconciliation are preserved without
overwrite. Response headers, redirect counts, and per-request HTTP evidence are
not recoverable from raw files alone. Exact-text extraction, grouping, labels,
validation/test opening, model scoring, and training remain closed. The next
permitted action is a separately reviewed offline result-finalization repair;
another archive request is not permitted by this state.

## Reproduction commands

From the repository root:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_sec_edgar_iapd_v11_supplemental_capture_reconciliation tests.test_sec_edgar_iapd_v11_supplemental_capture_execution -v
.venv\Scripts\python.exe -m scripts.reconcile_sec_edgar_iapd_v11_supplemental_capture --release configs/sec_edgar_iapd_v11_supplemental_capture_release_v1.json --release-qa D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_plan_v1\independent_release_qa_v1.json --reservation D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_result_v1\capture_report_v1.json --output D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_result_v1\raw_byte_reconciliation_v1.json
```
