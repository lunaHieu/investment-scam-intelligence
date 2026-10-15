# Project State and Gap Ledger V2

## Step and meaning

This ledger refreshes the project baseline after the complete raw-provenance audit. It prevents later work from following the stale V1 statement that the external 21-record gate and Target Text Corpus review had not yet progressed.

It is a registry-only state summary. It does not open validation/test data, access candidate domains, create labels, or run a model.

## Current verified state

| Branch | Verified state | Remaining gap | Next permitted work |
| --- | --- | --- | --- |
| Raw integrity/provenance | 278/278 existing raw files, 1,640,058,635 bytes, have Git-rooted SHA-256 chains; no existing-file mismatch | Two historical capture targets remain absent and explicitly excluded | Keep the V2 audit authoritative; rerun only after raw inventory changes |
| External 21-record intake | Owner-adopted AI reconciliation is complete: 10 `CONFIRMED`, 11 `LEGITIMATE`, 21 reporting-eligible | It is not independently human evidence-rereviewed gold; the legacy verifier is not module-compatible without a script-path import workaround | Preserve as an external diagnostic/reporting intake; repair tooling in a new verifier version only |
| Crimson | AI first pass covers 40; one human first review is recorded | 39 human first reviews, 21 second reviews, and 16 live-source gaps remain | Prepare bounded human packets; do not represent AI completion as human confirmation |
| Target Text Corpus pilot | 22 reviewable captures completed group, primary, blind-second, reconciliation, and owner acceptance; 4 `CONFIRMED`, 11 `LEGITIMATE`, 7 `UNCERTAIN` | The 15 decisive labels are diagnostic only; development corpus and split gates remain unmet | Use the pilot to refine acquisition and review policy, not as a completed V1-Core release |
| Source capacity / SEC-IAPD | 115 planned; 84 resolved; 31 frozen in exact V4 retry | Cooldown remains closed until 2026-10-16 00:48:55.969405 +07:00 | Execute V4 once after the gate; capture planning stays closed while unresolved rows remain |
| Vietnamese channel | Terms/source roles are registered; verified Vietnamese supply is 0 | At least 8 `CONFIRMED` and 8 `LEGITIMATE` Vietnamese groups are required; reuse basis/manual artifacts are missing | Prepare exact manual acquisition packet and wait for lawful source artifacts |
| Mendeley text model | 3,916 train rows / 3,783 groups; E5 development challenger rejected | Source/style geometry remains unresolved; no new encoder or tuning hypothesis is authorized | Preserve baseline; model-choice analysis may be documentary only |
| Image branch | Mendeley has no usable image assets | No compatible licensed image dataset | Keep image training closed |

## Updated work order

1. **P4 — Crimson human-review packet maintenance.** Keep the 39 first-review and 21 second-review obligations explicit. AI may prepare evidence summaries but cannot write human confirmation.
2. **P5 — Capacity completion.** Resume SEC/IAPD V4 only after its timestamp; in parallel prepare the Vietnamese/manual-source acquisition packet. Do not synthesize quota fillers.
3. **P7 — Model-choice dossier.** Compare model families against the verified data geometry, resource limits, language plan, and deployment needs without fitting or scoring a new model.
4. **P8 — Thesis/reproducibility documentation.** Update the data flow, provenance chain, review hierarchy, known exclusions, and limitations.

P2 is complete. P3 is complete as an owner-adopted AI-assisted diagnostic intake, not double-reviewed gold. P6 remains partly manual and should be advanced only through preparation until the user supplies the blocked artifacts.

## Closed gates

New training/configuration search, validation/test opening, external-holdout scoring, image training, live candidate-domain crawling, SEC/IAPD capture-plan preparation before complete availability QA, and automatic conversion of registry identity into ground truth remain closed.
