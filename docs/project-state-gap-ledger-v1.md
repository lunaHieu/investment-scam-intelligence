# Project State and Gap Ledger V1

## Step name

Freeze an offline, hash-bound snapshot of the project state before parallel work.

## Meaning

This ledger separates completed evidence from plans, blocked gates, and future
work. It reads only committed registries. It does not inspect validation or test
records, modify raw data, access a network, create labels, or run a model.

## Current state

| Branch | Verified state | Main gap | Permitted next work |
| --- | --- | --- | --- |
| Mendeley text | 3,916 train rows and 3,783 groups were used in the frozen four-fold OOF diagnostic; E5 was rejected at development | Source/style geometry and within-source imbalance remain stronger concerns than model capacity | Preserve the baseline and document evidence; any new model hypothesis requires a separate frozen protocol |
| External text | 21 AI reviews complete: 10 `CONFIRMED` recommendations and 11 `LEGITIMATE` recommendations | 0 human confirmations and 0 evaluation-eligible records | Explicit adoption, then separate reconciliation; no silent label conversion |
| Crimson | 40-row review plan; one first review recorded | 39 first reviews remain; 21 rows were planned for second review; 16 have live-source gaps | Review local evidence first and keep inaccessible-source cases blocked |
| V1-Core | Contract requires 300 balanced groups: 240 development and 60 external holdout | 0 real groups validated, 0 real split assignments, 0 train rows materialized | Measure channel/language deficits; do not synthesize quota fillers |
| SEC/IAPD Wayback | 115 candidates: 42 available, 42 unavailable, 31 unresolved | V4 cooldown is active | Resume the exact V4 release only after 2026-10-16 00:48:55 +07:00 |
| Image branch | Mendeley contains no image references or image files | No licensed compatible image dataset | Keep image training closed |
| Vietnamese channel | Source roles and terms are registered | No reference records acquired; manual export or written reuse basis is missing | Prepare a manual acquisition packet only |

## Parallel order

1. **P2 — Raw integrity and provenance QA.** Verify immutable raw files,
   manifests, hashes, schemas, row counts, and label semantics without changing
   raw bytes.
2. **P3 — External 21-record decision gate.** Record explicit adoption where
   justified, preserve `UNCERTAIN` otherwise, then run separate reconciliation.
3. **P4 — Crimson bounded review.** Finish locally supportable reviews first;
   isolate every case that needs unavailable live evidence and keep blind second
   review separate.
4. **P5 — V1-Core gap analysis.** Recompute deficits by target status, channel,
   language, and cohort. This is a capacity report, not a dataset release.
5. **P6 — Manual acquisition packets.** Prepare exact file, provenance,
   license/reuse, storage, and hash instructions for DFPI/CFTC/Vietnamese inputs;
   never bypass access controls.
6. **P7 — Model-choice dossier.** Compare model families against verified data
   properties without fitting, scoring, or opening any held-out partition.
7. **P8 — Thesis/reproducibility documentation.** Maintain the data-flow,
   evidence policy, split policy, and limitation narrative from frozen results.

V4 remains an independent timed branch. Its output may change the SEC/IAPD
capacity state later, but it does not block P2 through P8.

## Closed gates

Training, validation/test opening, external-holdout scoring, image training,
live-domain crawling, archive capture before complete availability QA, and
automatic conversion of registry identity into ground truth all remain closed.
