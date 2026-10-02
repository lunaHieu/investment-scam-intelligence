# Target Text Corpus V1 schema/review pilot

Status: **protocol and schema frozen; enumeration remains blocked**.

This phase defines exactly what the first balanced candidate wave will contain and how it will be reviewed. It does not create 40 labels. A candidate is only a provenance record pointing to a possible future Wayback website capture; it begins as `UNCERTAIN`, `LOW`, `UNREVIEWED`, and `training_eligible: NO`.

## Initial 40-candidate wave

| Target stratum | Channel | Initial candidates | Eligible-group target |
|---|---|---:|---:|
| `CONFIRMED` | Existing regulator-linked website | 10 | 10 |
| `CONFIRMED` | CFTC RED-linked Wayback website | 10 | 10 |
| `LEGITIMATE` | Existing SEC/IAPD-linked website | 10 | 10 |
| `LEGITIMATE` | SEC EDGAR-linked Wayback website | 10 | 10 |

The 40 candidates are a first wave, not a promise of 40 usable groups. Capture failures, weak identity linkage, duplicates, contradictions, or review disagreement can route records to `UNCERTAIN`. If a channel finishes below ten accepted independent groups, a separately frozen reserve wave adds five candidates from that same channel. A shortfall cannot be filled from another channel and cannot lower the gate.

## Deterministic selection

Eligible reference rows are ranked by the hexadecimal SHA-256 of the frozen seed, channel ID, source ID, source record ID, and normalized host. The lowest ten per channel form the initial wave. One reference record and one normalized host may appear only once; hosts may not cross channels, and entities may not cross target strata. Manual cherry-picking and model-score ranking are prohibited.

Before a row can enter the queue it must have an exact reference identifier and URL, a hash of the acquired reference artifact, an entity name, a candidate URL and normalized host, and a written identity-linkage basis. It must pass the opened-cohort host and reference-identity checks and the remediated legacy-component check. Exact capture, text, and near-duplicate checks remain pending until a Wayback artifact exists.

## Review sequence

1. Validate every candidate against `schemas/target_text_candidate.schema.json`.
2. Perform independent provenance QA before registering a frozen queue hash.
3. Query and capture only through Wayback; do not open live candidate domains.
4. Preserve immutable raw bytes, capture SHA-256, extracted UTF-8 text, and text SHA-256.
5. Re-run exact, host, identity, transitive-group, and near-duplicate exclusions.
6. Complete primary review.
7. Complete a blind independent second review without the first rationale or any model prediction.
8. Reconcile disagreements or retain `UNCERTAIN`.
9. Obtain owner acceptance and verify the pilot gate.

Binary eligibility requires a captured investment-related artifact, exact identity linkage, at least 20 non-whitespace characters, complete grouping, no opened-cohort overlap, `HIGH` confidence, `RECONCILED` review, independent second review, and owner acceptance. A warning-list entry or registry/filing reference alone is never sufficient.

## Current blockers

- CFTC channel: a manually acquired or explicit official-download RED reference artifact, path, and SHA-256 are still required.
- SEC EDGAR channel: a truthful project contact identity for the User-Agent and a frozen documented API/bulk manifest are still required.

The protocol forbids releasing only the two ready channels. All four inputs must be ready before the complete balanced wave is enumerated. This prevents source availability from silently changing class/channel composition.

No network operation, candidate enumeration, capture, label change, model operation, validation opening, or test opening occurred in this phase. Passing this pilot will validate the workflow only; it will not authorize model training.
