# SEC EDGAR/IAPD all-filer shortlist V2

## Step name

Create a bounded, deterministic, disjoint review shortlist.

## Meaning

The release selects 134 rows from the independently verified 1,129-row hashed identity pool: 107 for the development namespace and 27 for the fresh external-holdout namespace. Development is selected first; holdout is selected from the remaining rows with a different namespace-bound key.

Before selection, host hashes are excluded from ten prior queues or pools plus the opened-cohort exclusion index. The frozen preflight contains 660 unique historical host hashes, removes 53 overlapping crosswalk rows, and leaves 1,076 eligible rows. Selection is deterministic and does not use model scores or manual preference.

Only selected rows are joined back to their frozen IAPD host and URL. The shortlist remains `UNCERTAIN`, is not a ground-truth dataset, and authorizes no live-domain access, Wayback query, capture, label, or model operation.
