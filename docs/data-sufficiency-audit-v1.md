# Data Sufficiency Audit V1

Date: 2026-10-16  
Status: frozen offline documentary audit

## Purpose

This audit separates five quantities that must not be added together:

1. raw files that already exist and pass integrity checks;
2. historical benchmark rows eligible for the current internal baseline;
3. reference metadata used to discover or verify candidates;
4. diagnostic pilot decisions that remain outside the target release;
5. fresh evidence-backed target records admitted to the V1-Core release.

It performs no network access, labeling, model training, scoring, validation access, or test access.

## Audited state

### Existing raw storage

- 278 files, 1,640,058,635 bytes.
- 278/278 existing files are covered by verified hash-pinned provenance chains.
- This is **100% integrity coverage of the raw files currently stored**.
- It is **not** 100% completion of all planned acquisition. Pending sources and gated archive capture remain outside this denominator.

### Historical Mendeley benchmark

- Raw source rows: 16,202.
- Benchmark-eligible rows: 5,592.
- Frozen `group_split_v2`: 3,916 train, 838 validation, and 838 test rows.
- Train contains 3,783 disjoint groups.
- Auxiliary rows: 10,607; quarantine rows: 3. Neither class is eligible for benchmark training or scoring.
- At the current gate, only the 3,916 train rows are usable by the already authorized internal baseline workflow. Validation and test remain unopened for new experiments.

### Reference metadata, not training examples

- SEC EDGAR all-filer identity index: 988,519 entries.
- IOSCO warning reference index: 47,001 entries.
- IAPD reference index: 23,927 entries.

These entries are discovery/identity metadata. They are not captured text artifacts, evidence-backed labels, or model rows, and must never be summed into corpus or training totals.

### Fresh target-corpus evidence

The accepted V1-Core contract requires 300 disjoint groups: 240 DEVELOPMENT and 60 EXTERNAL_HOLDOUT, balanced across two labels and four channels (75 groups per channel).

- Records validated into the actual V1-Core release: **0/300 (0%)**.
- Target Text diagnostic pilot: 22 reviewed artifacts; 4 CONFIRMED, 11 LEGITIMATE, 7 UNCERTAIN. The 15 decisive outcomes remain diagnostic and do not satisfy the release quotas.
- External diagnostic pilot: 21 records (10 CONFIRMED, 11 LEGITIMATE), also outside Gold/train.
- Crimson raw domain records: 43,572. They are unlabeled discovery records; current training-eligible count is 0.
- Verified Vietnamese supply: 0.
- Usable image assets: 0.

### SEC EDGAR/IAPD acquisition pipeline

- Frozen candidate plan: 115 rows.
- Latest registered state before V5 execution: 92 resolved, comprising 45 archive-available and 47 unavailable; 23 unresolved.
- An availability result is not a captured raw artifact and does not establish a label.
- Therefore this branch has added 0 training-ready records so far. Capture planning remains closed until availability QA is complete.

## Decision

The project has enough historical data to maintain the current internal text baseline (3,916 train rows), but it does not yet have a completed fresh, evidence-backed target corpus. Existing raw integrity is complete for what is stored; planned acquisition is not complete.

Accordingly:

- do not report reference metadata, candidate URLs, availability rows, or diagnostic pilots as training records;
- keep the fresh target release at 0/300 until records pass capture, exact-text extraction, grouping, two independent evidence reviews, reconciliation, and release admission;
- keep new model selection/promotion and validation/test access closed;
- execute the SEC/IAPD V5 availability gate when its `not_before` time opens, then continue capture and review only through the committed gates.

## Practical progress measures

| Measure | Numerator / denominator | Status |
|---|---:|---:|
| Integrity of currently stored raw files | 278 / 278 | 100% |
| Current historical baseline train rows | 3,916 | available under frozen contract |
| Fresh V1-Core release groups | 0 / 300 | 0% |
| SEC/IAPD availability resolved | 92 / 115 | 80% |
| SEC/IAPD training-ready records | 0 | not started |

The percentages use different denominators and must be reported separately.
