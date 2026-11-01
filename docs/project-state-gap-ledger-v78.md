# Project State Gap Ledger V78

Date: 2026-11-01

## Current state

| Workstream | Verified state | Remaining gate |
|---|---|---|
| Crimson owner primary confirmation | 24 pre-existing READY recommendations confirmed by the owner. | Confirmation does not apply to later follow-up tasks. |
| Crimson single-review reconciliation | 16 identity/evidence-level reconciliations; model disposition remains `UNCERTAIN`. | No labels or admission. |
| Crimson blind second review | 9 packets ready; 0 completed. | A different human reviewer must return decisions without seeing primary decisions or AI suggestions. |
| Crimson second review waiting | 12 tasks wait for primary evidence review. | Review primary evidence first. |
| Crimson official-reference primary follow-up | 15 tasks remain pending. New V2 supplement adds 12 facts across 11 pilot IDs and 15 updated access statuses. | Human primary decision required; root-only/name-only relationships remain unclear. |
| Crimson official-source access blockers | Direct source access remains unresolved for the FMA entries Benefittrade and Banktrustcoin and the CONSOB entry Magnomic Yield. | Use a user-supplied official copy or an authorized direct channel; do not retry the blocked URL or bypass bot protection. |
| PBC05/PBC08 | Offline closeout V2 passed; PBC05 attempt count 3; PBC08 attempt count 2; exact causes not fully recoverable. | Same-release retry remains closed. No malware scan result exists. |
| PBC06/PBC07 | Provenance/documentation only. | No dataset rows. |
| Data admission / labels / training | 0 rows admitted; 0 labels; 0 training-eligible records. | Keep closed until source, evidence, human review, required blind review, reconciliation, and owner acceptance are recorded. |

## Pinned current navigation

- Direction: `docs/project-direction-plan-r41.md`.
- Reproducibility guide: `docs/reproducibility-current-state-v75.md`.
- Machine-readable reproducibility state:
  `registry/analyses/reproducibility_current_state_v75.json`.
- Crimson official-source supplement and independent QA:
  `registry/analyses/crimson_official_source_followup_v2.json` and
  `registry/analyses/crimson_official_source_followup_v2_qa.json`.
- PBC offline closeout and QA:
  `registry/analyses/pbc05_pbc08_offline_closeout_v2.json` and
  `registry/analyses/pbc05_pbc08_offline_closeout_v2_qa.json`.

## Review order

1. Record human primary decisions against the pinned official facts. Preserve
   `UNCERTAIN` for insufficient or conflicting evidence.
2. Send blind packets to an independent human reviewer with primary decisions
   and AI suggestions omitted.
3. Reconcile only after required reviews are complete.
4. Admit data only after evidence, review, reconciliation, and owner acceptance
   are recorded.

## Latest verification expected in V78

- Official-source supplement focused tests: 3 passed.
- Registry validation: 418 analysis registries.
- Current full test suite V10: 1,200 passed, 0 failed.
- Candidate-domain access: 0; raw official pages retained: 0; labels and
  admitted data rows: 0.
