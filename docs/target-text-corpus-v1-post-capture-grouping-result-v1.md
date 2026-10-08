# Target Text Corpus V1 — post-capture grouping result V1

The automated offline gate compared all 22 minimum-content artifacts against the 107 opened external-cohort records and grouped the pilot internally. Independent QA reimplemented normalization, pair scoring, overlap lookup, and graph components using breadth-first search; all 23 emitted records matched exactly.

No pilot artifact shares an exact raw-capture hash, exact text hash, or exact normalized-host hash with an opened record. No candidate-to-opened or candidate-to-candidate pair meets the frozen normalized five-token-shingle threshold. The 22 minimum-content artifacts therefore remain 22 separate provisional transitive exclusion groups, with no group spanning the two target source strata.

| Result | Count |
|---|---:|
| Manifest records audited | 23 |
| Minimum-content artifacts compared | 22 |
| Opened cohort records compared | 107 |
| Automated exact/host overlap exclusions | 0 |
| Opened near-duplicate review routes | 0 |
| Candidate-internal near-duplicate pairs | 0 |
| Provisional transitive groups | 22 |
| Cross-stratum groups | 0 |
| Below-minimum artifacts retained outside review | 1 |
| Labels created | 0 |

This result means only that no overlap was found by the frozen exact and normalized rules. It does not prove the absence of semantic clones, shared control, campaigns, or cross-domain case relationships. Manual cross-domain case/clone/group review remains mandatory before primary case and label review may begin.

No network request, live-domain access, model operation, or validation/test opening occurred.
