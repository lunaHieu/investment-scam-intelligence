# Target Text Corpus V1 — post-capture exclusion and grouping V1

This offline gate compares the 22 minimum-content pilot artifacts with all 107 records in the opened external-cohort exclusion index. It also assigns deterministic technical groups across the pilot before any case or label review.

Exact overlap checks use raw-capture SHA-256, exact UTF-8 text SHA-256, and the already frozen normalized-host SHA-256. Near-duplicate screening normalizes Unicode with NFKC/casefold, masks URLs, emails, and numeric values, and compares five-token shingle sets. A pair is flagged when Jaccard similarity is at least 0.80, or when the shorter side has at least 20 shingles and at least 0.95 of those shingles are contained in the longer side.

Candidate-internal groups are connected transitively through exact source reference, normalized reference entity, exact normalized host, exact text, and the frozen near-duplicate rule. These identifiers exist only to control exclusion and future split leakage. They are not evidence-backed real-world case, campaign, entity, or legal findings.

An exact opened-cohort capture, text, or host match is excluded. A probable normalized near-duplicate with an opened cohort is routed to manual cross-domain clone review. A clean automated result still requires manual case/clone/group review before primary label review may start.

This stage performs no network request, accesses no live candidate domain, creates no label, runs no model, and opens no validation or test partition.
