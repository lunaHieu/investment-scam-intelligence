# Target text corpus v1: primary case-and-artifact review result

## Result

The frozen local-evidence packet covered all 22 minimum-content artifacts. Primary review produced:

- 4 `CONFIRMED` recommendations;
- 11 `LEGITIMATE` recommendations;
- 7 `UNCERTAIN` recommendations;
- 0 ground-truth labels; and
- 0 training-eligible records.

The structural verifier passed the exact population, required assessment fields, conservative decision gates, supporting facts, rationales, summary counts, and safety scope.

## Conservative routes

The seven uncertain records were not forced into their source strata:

- `TTCV1_CAND_CONF_CFTC_006`: expired-domain parking notice, no target artifact;
- `TTCV1_CAND_CONF_CFTC_009`: unrelated petroleum-equipment content and identity conflict;
- `TTCV1_CAND_CONF_REG_008`: solar-technology content plus a long warning-to-capture gap;
- `TTCV1_CAND_CONF_REG_009`: fund-recovery service rather than an investment offer;
- `TTCV1_CAND_LEGIT_EDGAR_007`: banking super-app capture does not expose the registered adviser identity or investment service;
- `TTCV1_CAND_LEGIT_IAPD_007`: Ironwood Funding/irfcapital identity does not resolve to Cumberland Hill Capital Management; and
- `TTCV1_CAND_LEGIT_IAPD_008`: Astō Consumer Partners is not explicitly connected to Christopher & Co LLC in the frozen artifact.

## Interpretation

These are primary recommendations only. They are intentionally stored beside `ground_truth_status = UNCERTAIN`, `label_created = false`, and `training_eligible = NO`. A passing structural QA does not validate the factual judgments or convert recommendations into labels.

## Next gate

Construct a blind second-review packet that omits every primary recommendation, assessment, rationale, and summary. A separately recorded pass must review all 22 artifacts from the same frozen evidence. Only after disagreement reconciliation and owner acceptance may any eligible label be materialized.
