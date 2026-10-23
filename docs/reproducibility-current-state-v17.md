# Reproducibility Current State V17

Date: 2026-10-23

Authoritative ledger: `registry/analyses/project_state_gap_ledger_v20.json`

Current navigation adds
`registry/analyses/target_text_corpus_v1_ready_channel_queue_v1.json` to the
A1/A2 archive, A4 admission-repair, and B1 capacity records.

B2 deterministically materialized and independently reproduced 70 fresh
provenance candidates: 50 development and 20 external-holdout rows, split
equally between the two ready channels. All candidate IDs, hosts, and normalized
entities are unique. Development and holdout have no host or entity overlap.

Current established counts are:

- 113/115 SEC/IAPD archive availability identities resolved;
- 57/58 SEC/IAPD capture rows completed;
- 56 SEC/IAPD reviewable records;
- 42 owner-accepted `LEGITIMATE`, 14 `UNCERTAIN`;
- 0/300 V1-Core groups admitted;
- 70 B2 provenance candidates, all `UNCERTAIN` and uncaptured;
- zero training-eligible fresh records.

B2 performed no network request, candidate-domain access, Wayback query,
capture, label creation, validation/test opening, scoring or training.
