# Reproducibility Current State V18

Date: 2026-10-23

Authoritative ledger: `registry/analyses/project_state_gap_ledger_v21.json`

Current navigation adds
`registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_plan_v1.json`
to the established A1/A2, A4, B1, and B2 records.

B3 materialized and independently verified 70 archive-only availability plan
rows. They preserve the 50/20 development/external-holdout split and the exact
B2 order. Each request URL round-trips to its source candidate and targets only
the archive availability endpoint with target date `20261003`.

Current established counts are:

- 113/115 SEC/IAPD archive availability identities resolved;
- 57/58 SEC/IAPD capture rows completed;
- 56 SEC/IAPD reviewable records;
- 42 owner-accepted `LEGITIMATE`, 14 `UNCERTAIN`;
- 0/300 V1-Core groups admitted;
- 70 B2 provenance candidates, all `UNCERTAIN`;
- 70 B3 availability plan rows, none executed;
- zero training-eligible fresh records.

B3 performed no network request, live-domain access, Wayback query, capture,
label creation, validation/test opening, scoring, or training.
