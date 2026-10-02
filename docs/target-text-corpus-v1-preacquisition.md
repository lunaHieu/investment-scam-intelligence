# Target Text Corpus V1 pre-acquisition gate

Status: **offline inventory complete; capture remains blocked**.

This gate creates two artifacts required by the frozen Target Text Corpus V1 protocol before any new record is captured or labeled:

1. a provenance-only candidate-source inventory; and
2. a label-free exclusion index for every opened external cohort.

No domain was accessed, no record was downloaded or captured, no label was created or changed, no model was fitted or scored, and no validation/test partition was opened.

## Candidate-source inventory

The inventory contains no candidate records. It resolves only source-level provenance already present in `registry/sources.json` and separates four planned acquisition channels:

| Planned target status | Channel | Current readiness |
|---|---|---|
| `CONFIRMED` | Regulator-linked website artifacts | Provenance enumeration only |
| `CONFIRMED` | Corroborated case seeds for website/post/message artifacts | Blocked pending corroboration and capture-source protocol |
| `LEGITIMATE` | Official-register-linked website artifacts | Provenance enumeration only |
| `LEGITIMATE` | Official-account post/message artifacts | Blocked pending platform-source registration and terms review |

Two channels are planned per target status, but only one channel per status is currently ready even for provenance enumeration. The required two-channel gate therefore fails. This is expected and prevents early source concentration from being hidden.

Mendeley V2 remains a historical heterogeneous benchmark. MultiAgentFraudBench remains synthetic-only. Neither is a candidate source for case-level target ground truth.

## Opened-cohort exclusion index

The index covers all four opened external cohorts and 107 records. It emits no artifact text and no per-record ground-truth status. Domains and URLs are stored only as SHA-256 exclusion keys.

| Coverage item | Result |
|---|---:|
| Opened cohorts | 4 |
| Opened records | 107 |
| Unique capture hashes | 98 |
| Unique text hashes | 96 |
| Unique normalized-host hashes | 94 |
| Records with formal `case_id` | 21 |
| Records missing formal `case_id` | 86 |
| Records with formal case/campaign and near-duplicate groups | 21 |

The index also records nine duplicate-capture groups, eleven duplicate-text groups, and thirteen repeated normalized-host groups. These overlaps are primarily between the reconciled pilot and matched Wayback V1 and must be treated as one exclusion family when future candidates are checked.

Exact capture, exact text, and normalized-host exclusion are complete. A normalized host is not claimed to be a registrable domain family. Case-level, registrable-domain-family, and normalized near-duplicate exclusion are not complete because the frozen V1/V2/V3 benchmark schemas did not carry formal `case_id`, case/campaign group, or near-duplicate group fields for 86 records. The index preserves every identifier that does exist and marks every legacy gap explicitly; it does not invent evidence-backed case identities.

## Gate decision

New candidate capture and labeling remain blocked. The next offline step is to build and independently verify a legacy grouping-remediation map for the 86 records, using frozen source-candidate IDs, exact hashes, repeated-domain families, and available upstream provenance. Separately, the two blocked acquisition channels require registered capture sources and terms-reviewed protocols.

Training and deployment remain prohibited.
