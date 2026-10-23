# Reproducibility Current State V19

Date: 2026-10-23

Authoritative ledger: `registry/analyses/project_state_gap_ledger_v22.json`

Current navigation adds
`registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_execution_v1.json`
to the established A1/A2, A4, B1-B3 records.

B4 prepared and independently verified a crash-safe executor and timed release
for the exact 70 B3 availability rows. The release preserves the 50/20
development/external-holdout split, one-attempt limit, 60-second minimum
pacing, no-overwrite rule, and non-resumable partial-journal contract.

Current established counts are:

- 113/115 SEC/IAPD archive availability identities resolved;
- 57/58 SEC/IAPD capture rows completed;
- 56 SEC/IAPD reviewable records;
- 42 owner-accepted `LEGITIMATE`, 14 `UNCERTAIN`;
- 0/300 V1-Core groups admitted;
- 70 B2 provenance candidates, all `UNCERTAIN`;
- 70 B3 availability plan rows;
- 70 B4 release rows, none executed;
- zero training-eligible fresh records.

B5 is not authorized now. It requires a successful independently verified A1
result and must wait until the later of `2026-10-25T00:00:00+07:00` and A1's
actual report creation time plus 24 hours. B4 performed no network request,
live-domain access, Wayback query, capture, label creation, validation/test
opening, scoring, or training.
