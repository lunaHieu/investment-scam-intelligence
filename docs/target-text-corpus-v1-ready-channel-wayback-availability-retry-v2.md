# Ready-channel Wayback availability adaptive retry V2

This stage preserves the immutable first B5 report and prepares a separate
retry for the same ordered 70-row availability cohort. The first release made
one request, received HTTP 429 without `Retry-After`, finalized its report, and
left all 70 rows unresolved. It must not be rerun or overwritten.

The retry is governed by `ISI_ARCHIVE_RETRY_POLICY_V1`. A first HTTP 429
without a server-provided gate uses a bounded 15-minute delay, so this release
opens at `2026-10-26T09:48:38.369187+07:00`. The universal 24-hour fallback is
not used. The retry has its own release, independent QA, partial journal, final
report, and result QA.

The cohort remains exactly 70 ordered rows: 50 `DEVELOPMENT` and 20
`EXTERNAL_HOLDOUT`. Execution uses 60-second minimum pacing, one attempt per
candidate, stops on the first HTTP or transport error, records selected
diagnostic headers, never resumes a partial automatically, and never
overwrites an existing output. It contacts only the archive availability
endpoint. It does not contact candidate domains or download archived pages.

Verification and execution:

```powershell
.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v2 --release configs/target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v2.json
.venv\Scripts\python.exe -m scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_retry_v2 --release configs/target_text_corpus_v1_ready_channel_wayback_availability_retry_release_v2.json --release-qa D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_availability_plan_v1\independent_retry_release_qa_v2.json --verify-only
```

Capture planning remains closed until the independent retry result QA reports
complete availability resolution. Labels, model validation/test data,
scoring, and training remain outside this acquisition stage.
