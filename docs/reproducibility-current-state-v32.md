# Reproducibility current state V32

V32 records the independently verified B5 V2 coordination amendment for the
exact-70 ready-channel Wayback availability plan.

The immutable V1 release and plan remain unchanged: 70 unique hosts/entities,
50 `DEVELOPMENT`, 20 `EXTERNAL_HOLDOUT`, 35 regulator-linked candidates, and
35 IAPD-linked candidates. No availability request has yet been made.

A1 is now bound through its canonical-empty V2 QA. The archived report proves
HTTP 200, `application/json`, exact `[]\n` bytes, no HTTP 429, and no retry
need. The old V1 requirement that A1 contain no parser error and the missing
old QA filename are replaced by this immutable evidence. The inherited gate
ended at `2026-10-25T00:00:00+07:00` and is open.

B5 must execute once through
`scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v2`.
It reuses the hash-pinned V1 crash-safe `run_plan`: 60-second minimum pacing,
one attempt per candidate, pre-network journal, stop on the first error,
diagnostic-header preservation, atomic finalization, no overwrite, and no
automatic resume. Any failure is handled by the adaptive retry policy rather
than a new universal 24-hour release.

This availability action downloads no archived page and creates no label.
Capture, validation/test opening, scoring, and training remain closed.
