# Dataset V1-Core sampling matrix V1

This matrix freezes the next fresh target-corpus milestone at 240 development groups and 60 untouched external-holdout groups. The sampling unit is the transitive case/campaign, entity/domain-family, and near-duplicate group—not an individual row.

## Quotas

| Target status | Channel | Development | External holdout | Total accepted groups |
|---|---|---:|---:|---:|
| `CONFIRMED` | Regulator-linked archived website | 60 | 15 | 75 |
| `CONFIRMED` | CFTC RED-linked archived website | 60 | 15 | 75 |
| `LEGITIMATE` | SEC IAPD-linked archived website | 60 | 15 | 75 |
| `LEGITIMATE` | SEC EDGAR-linked archived website | 60 | 15 | 75 |

Each label therefore uses two acquisition channels, and no channel contributes more than 50% of either label. Shortfalls cannot be borrowed from another channel or label. The 22-record opened pilot and every Mendeley record contribute zero groups to these quotas.

All four channels use the same Wayback archived-website capture stratum. Warning text, registry text, source IDs, evidence metadata, and review rationale are never model inputs. Only observed artifact visible text may enter a future text model.

## Capacity audit

The pilot produced decisive-label yields of 20% for each confirmed channel, 40% for IAPD, and 70% for EDGAR. Applying those observed yields plus a 25% planning buffer gives candidate-reservoir estimates of 469, 469, 235, and 134 respectively. These are planning values, not promised labels; yield is recomputed after every frozen wave.

The existing regulator pool and IAPD pool pass that planning check. The current CFTC pool has only 12 eligible hosts versus a planning requirement of 469, and the current EDGAR pool has 20 versus 134. Candidate acquisition therefore remains blocked. The deficit cannot be hidden by drawing more examples from the two larger pools.

## Language and review

Each development label must contain at least 12 non-English groups, including at least 6 Vietnamese groups. Each external-holdout label must contain at least 3 non-English groups, including at least 2 Vietnamese groups. These coverage targets do not replace class or channel quotas, and current multilingual supply has not yet been audited.

Every binary-eligible artifact still requires immutable capture/text hashes, complete transitive grouping and opened-cohort exclusions, `HIGH` confidence, primary review, blind independent second review, reconciliation, and project-owner acceptance. `UNCERTAIN` remains outside binary fitting and evaluation.

## Next gate

Replenish and hash-audit the CFTC and EDGAR channel pools—or freeze terms-reviewed channel amendments without changing the 50% cap—and audit multilingual supply. Only then may fresh development candidates be enumerated. Holdout candidates must come from a separate namespace and acquisition wave and must be frozen before the first target-model candidate is selected.

This step performs no network access, candidate enumeration, capture, labeling, model fitting, scoring, or validation/test opening.
