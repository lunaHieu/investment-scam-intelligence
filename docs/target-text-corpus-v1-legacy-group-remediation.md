# Target Text Corpus V1 legacy grouping remediation

Status: **independent offline recomputation passed; candidate capture remains blocked**.

This step remediates the grouping metadata gap identified in the pre-acquisition audit. It does not create evidence-backed cases, labels, captures, model inputs, or model results.

## Scope and method

The opened-cohort exclusion index contains 107 records. Twenty-one reconciled-pilot records already have formal `case_id`, case/campaign group, and near-duplicate group fields. The remaining 86 records from the matched Wayback V1, language V2, and holdout V3 benchmarks do not.

All 86 legacy records joined exactly to their frozen upstream candidate-queue record through `source_candidate_id == candidate_id`. The remediation then formed connected components over all 107 opened records using only three equality edges:

- exact capture SHA-256;
- exact text SHA-256; and
- exact normalized-host SHA-256.

The component algorithm is transitive. Group IDs are deterministic hashes of sorted component record keys. A group ID is an exclusion-control identifier only; it is not a real-world case ID, registrable domain family, label, or legal finding.

## Results

| Result | Count |
|---|---:|
| Opened records processed | 107 |
| Legacy records remediated | 86 |
| Exact upstream queue joins | 86 |
| Components across all opened records | 94 |
| Components containing legacy records | 86 |
| Legacy records anchored to an existing frozen case | 13 |
| Legacy records remaining exclusion-only and unanchored | 73 |
| Formal case IDs created | 0 |
| Labels created or changed | 0 |

The 13 anchored records share exact capture, text, or normalized-host metadata with a reconciled-pilot record carrying an existing case ID. This establishes an exclusion linkage only. It does not repeat or replace the original evidence review.

The other 73 records retain their exact queue provenance and receive stable singleton exclusion groups. They are intentionally marked `LEGACY_EXCLUSION_ONLY_UNANCHORED`; no upstream `source_case_id` is promoted to a formal case ID.

## Independent review

The independent checker does not import the builder. It uses a separate bucket-adjacency and breadth-first-search implementation to recompute all components, queue joins, group IDs, anchor lists, and per-record output fields.

The checker compared all 86 emitted records and reproduced:

- 94 components;
- 86 queue joins;
- 13 anchored records; and
- 73 unanchored exclusion-only records.

No discrepancy was found. The checker also confirmed that remediation records contain no artifact text and no per-record ground-truth status.

## Remaining gate

Legacy exclusion-group assignment is complete, but evidence-backed case linkage is intentionally partial. Future candidates still require manual cross-domain case/campaign and clone review; a matching or non-matching technical group cannot determine a label.

New candidate capture and labeling remain blocked. The next gate is to register and terms-review capture protocols for the two blocked acquisition channels identified by the candidate-source inventory. Training and deployment remain prohibited.
