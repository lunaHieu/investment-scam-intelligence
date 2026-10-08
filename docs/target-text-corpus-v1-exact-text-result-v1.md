# Target Text Corpus V1 — exact-text result V1

## Outcome

The offline extractor produced 23 immutable UTF-8 text files from the 23 audited Wayback captures. Independent QA regenerated every text artifact from its raw capture and matched all 23 output files byte-for-byte, including their SHA-256 hashes and the exact output file set.

Twenty-two artifacts meet the frozen minimum of 20 non-whitespace characters. `TTCV1_CAND_CONF_CFTC_008` contains zero visible characters under the frozen extractor, so its empty text artifact is preserved for audit but routed out of the reviewable population as `BELOW_MINIMUM_PRESERVED`. It is not replaced, repaired, or treated as class evidence.

| Check | Result |
|---|---:|
| Raw captures presented to extraction | 23 |
| UTF-8 text files written | 23 |
| Independent byte-for-byte matches | 23 |
| Minimum-content pass | 22 |
| Below minimum, preserved | 1 |
| Gzip payloads decoded | 6 |
| Identity payloads decoded | 17 |
| Raw files modified | 0 |
| Labels created | 0 |
| Model operations | 0 |

Minimum-content passes by channel are 4 CFTC-linked confirmed candidates, 4 regulator-linked confirmed candidates, 6 IAPD-linked legitimate candidates, and 8 SEC EDGAR-linked legitimate candidates. These are candidate source strata, not accepted binary labels.

## Gate decision

Exact-text extraction and independent QA pass. Post-capture exclusion and transitive grouping may now run on the 22 minimum-content artifacts. Human label review remains closed until exact capture/text, opened-cohort, host/domain-family, case/campaign, and near-duplicate exclusion checks have been applied and independently verified.

No live domain was accessed, no validation or test data was opened, and no model was fit or scored.
