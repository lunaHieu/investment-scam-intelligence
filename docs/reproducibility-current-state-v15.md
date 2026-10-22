# Reproducibility Current State V15

Date: 2026-10-23  
Authoritative ledger: `registry/analyses/project_state_gap_ledger_v17.json`

## Current navigation

Use these registries for the active state:

- `registry/analyses/sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1.json`;
- `registry/analyses/sec_edgar_iapd_wayback_availability_v11_protocol_v1.json`;
- `registry/analyses/target_text_corpus_v1_capacity_gap_v4.json`;
- `registry/analyses/project_state_gap_ledger_v17.json`.

A1 still has a verified concrete CDX release waiting for its timed gate. A2
still has verified V11 tooling but no concrete release. A3 is complete and
made no network request: V1-Core is 0/300 admitted, has 42 owner-accepted
conditional candidates, and has a conditional residual gap of 258 groups.

The 43,572 Crimson domains, 278 integrity-verified raw files, 3,916 historical
baseline train rows, reference inventories and image metadata are separate
denominators. None is silently counted toward V1-Core. Human-reviewed language
credit is zero; the minimum gap is 30 non-English groups including 16
Vietnamese groups. Usable image assets are zero, which keeps multimodal work
closed but does not block the text-only V1-Core contract.

No live candidate domain, archive page, label, validation/test partition,
model score or training operation was opened by A3.
