# Ready-channel Wayback availability retry V3

The first adaptive B5 retry executed once at its 15-minute gate. Its final
report and independent QA preserve one HTTP 429 response, no `Retry-After`, no
partial journal, and all 70 rows unresolved. The V2 release cannot be rerun.

`ISI_ARCHIVE_RETRY_POLICY_V1` classifies this as the second consecutive HTTP
429 for the triggering row. Its bounded schedule opens the next release one
hour after the preserved report time: `2026-10-26T10:49:40.978852+07:00`.
This is not a universal 24-hour wait.

V3 is a separate exact-70 release with its own QA and output. It preserves the
original order and cohorts (50 `DEVELOPMENT`, 20 `EXTERNAL_HOLDOUT`) and uses
the same archive-only, 60-second, crash-safe, one-attempt-per-row execution
contract. This is the third and final identical network attempt for
`TTCV1_B3_AVAIL_001`. If that row receives HTTP 429 again, another identical
retry for it is forbidden; it must be quarantined while independent remaining
work is split out instead of extending an unbounded retry chain.

V3 performs availability metadata queries only. It does not contact candidate
domains, download archived page bytes, label records, open validation/test
data, score models, or train models. Capture planning remains closed until a
complete independently verified availability result exists.
