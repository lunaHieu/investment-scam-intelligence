# Reproducibility current state V30

V30 records a separately frozen metadata-recovery release for the two V11
supplemental rows whose prior capture preserved raw bytes but omitted the HTTP
response metadata needed for strict capture QA. This release is independent of
the historical capture result and uses new output paths.

## Current state

- Availability remains 115 resolved rows: 60 available and 55 unavailable.
- The original 58-row capture, 56-row review/reconciliation, and owner
  acceptance remain immutable: 42 `LEGITIMATE`, 14 `UNCERTAIN`, training
  eligibility zero.
- The prior two-row supplemental raw-byte repair remains
  `PASS_REPAIRED_RAW_BYTES_METADATA_INCOMPLETE_EXTRACTION_CLOSED`.
- A new exact-two-row metadata-recovery plan and archive-only release are
  independently verified. The ordered identities are
  `TTCV1_EDGAR_AVAIL_HOLDOUT_011` and `TTCV1_EDGAR_AVAIL_HOLDOUT_018`.
- The recovery release gate is
  `2026-10-27T08:42:13.975064+07:00` Asia/Saigon. Its raw-output directory is
  separate from both the historical reservation and the repaired raw files.
- Release QA is `PASS_ARCHIVE_ONLY_V11_METADATA_RECOVERY_RELEASE`; no network
  operation has been performed for this release.
- An independent recovery-result verifier and a separate exact-text release
  builder/verifier are prepared. The exact-text builder remains closed until a
  complete metadata-verified recovery result exists.

## Gate decision

The recovery executor is prepared but gate-closed. Before the gate, no archive
request, candidate-domain request, report creation, raw-file write, exact-text
extraction, grouping, labeling, validation/test opening, scoring, or training
is allowed. At the gate, execution remains one attempt per row, raw
`web.archive.org` replay only, a minimum 30-second delay, stop on HTTP 429,
pre-network partial reservation, and no overwrite/automatic resume.

The recovery result, if later produced, will be supplemental and cannot be
merged into the frozen 58-row capture or 56-row accepted review population.

## Reproduction

```powershell
.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_v11_metadata_recovery_release --release configs/sec_edgar_iapd_v11_metadata_recovery_release_v1.json --output D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_metadata_recovery_plan_v1\independent_release_qa_v3.json
.venv\Scripts\python.exe -m scripts.execute_sec_edgar_iapd_v11_metadata_recovery --release configs/sec_edgar_iapd_v11_metadata_recovery_release_v1.json --release-qa D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_metadata_recovery_plan_v1\independent_release_qa_v3.json --verify-only
```
