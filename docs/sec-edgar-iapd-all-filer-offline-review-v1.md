# SEC EDGAR/IAPD all-filer offline review V1

## Step name

Materialize shortlist-only SEC evidence and review provenance and identity offline.

## Meaning

This gate reads only the 134 `CIK##########.json` members named by the frozen shortlist from the immutable SEC bulk ZIP. Their original bytes are preserved in a bounded evidence directory. The process verifies ZIP-member CIK, JSON CIK, SEC name, IAPD record ID, IAPD host, candidate URL, cohort, and all pre-capture safety states.

Identity review is deliberately conservative. Names equal after punctuation, leading-article, and legal-suffix normalization receive an exact-name evidence result. Non-exact pairs with at least 0.8 full-token Jaccard receive a compatible-variant result. Other rows that passed the earlier distinctive-token crosswalk remain cautions and cannot advance to capture planning without deeper review. None of these states is a `LEGITIMATE` ground-truth label.

The operation is entirely local. It performs no live-domain access, Wayback query, website capture, label creation, validation/test opening, or model operation.

## Result

All 134 selected ZIP members were found, extracted byte-for-byte, and matched to their frozen CIK and SEC name. The IAPD record, normalized host, candidate URL host, and host hash also matched for every row. Conservative name review produced 114 exact-core passes, one compatible variant, and 19 ambiguous related-name cautions. The 115 pass/compatible rows may be considered in a later capture-planning review, but this result itself authorizes no capture. The 19 cautions remain on hold for deeper identity evidence.

An independent verifier reproduced the exact member set, byte hashes, source joins, review classifications, counts, and closed gates for all 134 rows.
