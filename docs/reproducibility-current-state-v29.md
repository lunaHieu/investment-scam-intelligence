# Reproducibility current state V29

V29 records the completed offline repair of the V11 supplemental capture
finalization failure. The repair is deliberately metadata-limited: it proves
that the two frozen plan identities map to present raw files and recomputed
SHA-256 hashes, but it does not recreate HTTP response headers or redirects.

## Current state

- Availability: 115 total rows resolved; 60 available and 55 unavailable.
- Original snapshot: 58-row capture, 56-row review, and owner acceptance remain
  immutable (42 `LEGITIMATE`, 14 `UNCERTAIN`, training eligibility zero).
- Supplemental repaired report: 2 ordered `EXTERNAL_HOLDOUT` rows, raw-byte
  hashes independently verified.
- Repaired QA: `PASS_REPAIRED_RAW_BYTES_METADATA_INCOMPLETE_EXTRACTION_CLOSED`.
- Capture QA in the strict HTTP sense remains closed because the executor did
  not persist response metadata.

## Gate decision

No recapture was performed. Exact-text extraction, grouping, labels,
validation/test opening, model scoring, and training remain closed. The repaired
artifact is supplemental evidence only and cannot silently join the frozen
56-row snapshot.

## Reproduction

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_v11_supplemental_capture_repaired_result --release configs/sec_edgar_iapd_v11_supplemental_capture_release_v1.json --report D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_result_v1\capture_report_v1.repaired.json --output D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_result_v1\independent_capture_qa_v1.repaired.json
```
