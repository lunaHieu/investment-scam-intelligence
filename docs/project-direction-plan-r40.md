# Project Direction Plan R40

Date: 2026-11-01

Base commit: `925777714117cbcf2c446742f671213160a9d62a`

## Work completed in this update

### Crimson review workflow

The project owner stated that they had reviewed Crimson and agreed with its
decision. That statement is recorded as confirmation of the **24 already
readiness-passed primary recommendations only**. It does not cover the 15 rows
that still require official-reference follow-up, and it is not represented as
an independent second review.

- 24 primary confirmations are recorded in a separate, hash-pinned snapshot.
- 16 rows whose plan requires only one review have an identity/evidence-level
  reconciliation. Their model-label disposition remains `UNCERTAIN`; no labels
  or training eligibility were created.
- Nine blind second-review tasks are ready: the prior `PILOT_CRIMSON_REF_018`
  task plus eight rows newly confirmed by the owner. Packets omit AI and
  primary-review decisions. A genuinely independent human reviewer is still
  required.
- Twelve double-review tasks remain waiting on primary review. Fifteen primary
  tasks remain open because the official-reference follow-up gate was not
  closed.

Six official regulator pages were read and their relevant facts recorded in a
small evidence manifest: BitForex/SFC, Ai-MiningEx/FCA,
Chainstackinvest.com/FCA, OPENTRADING PLATFORM/FCA, PrimeWealth/AMF Québec,
and Trade Xtix Coins/SEC. The manifest is linked to the exact official URLs;
raw page files were not retained. The other URL occurrences remain blocked,
unconfirmed, or without a matching target in the saved view. The same failed
URLs were not retried. All 15 follow-up rows remain open pending human review.

No Crimson candidate host was accessed. No evidence or identity assessment
was materialized as a `SCAM` or `LEGITIMATE` label. Data admission and training
remain closed.

### PBC05/PBC08 offline closeout

The cross-version audit separates three PBC result snapshots and corrects an
important row-count distinction:

- PBC05 has three actual attempts across the snapshots. Its two instrumented
  attempts used the same PDF response hash but captured different stderr sizes
  and hashes (759 bytes and 710 bytes). The exact cause is unrecoverable from
  retained hashes.
- PBC08 has two actual attempts. It was `SKIPPED_AFTER_FAILURE` in the earliest
  result, not requested there. The later diagnostic result confirms the
  forbidden-dataset-key guard, but not the key name/path/value.
- The offline PBC V2 closeout QA independently passed these checks. No source
  request was made. No malware scan result exists, so the data cannot establish
  either malware presence or absence.
- PBC06/PBC07 remain metadata/documentation provenance only; zero rows were
  admitted.

Same-release PBC retries remain prohibited. Any future revisiting requires a
new technical release, independent QA, and scoped owner authorization.

## Verification

- Crimson owner-progress QA: 24 primary confirmations, 16 single-review
  reconciliations, nine blind handoff tasks, six official-page fact records,
  and 15 open official-reference tasks verified; zero blind-field leaks.
- PBC offline closeout QA: pass; PBC05/PBC08 attempt history checked against
  their immutable result hashes.
- Registry validation: 412 analysis registries valid.
- Current full suite V10: 1,197 passed, 0 failed.
- Candidate-domain requests, source downloads, dataset admissions, labels,
  validation/test access, model training and scoring: zero.

## Remaining work and order

1. Assign the nine ready blind second-review tasks to a different human who
   cannot see the primary decisions or AI suggestions; collect row-level
   decisions and preserve `UNCERTAIN` for missing or conflicting evidence.
2. Obtain the official documents or permitted access needed for the 15 open
   primary tasks. Six have partial regulator-source facts recorded; the
   remaining listed URLs still need permitted access or a saved official copy.
   Do not retry the URLs marked blocked/rate-limited under the same access
   attempt.
3. Record any new primary reviews. Regenerate a separate task snapshot only
   after the source evidence and review decisions are pinned.
4. Reconcile double-review rows only after the blind reviewer responds. A
   disagreement or insufficient evidence remains `UNCERTAIN`.
5. Keep row admission and label materialization closed until source identity,
   evidence, primary review, required second review, reconciliation, and
   owner acceptance are all recorded.

Machine-readable state: `registry/analyses/project_state_gap_ledger_v77.json`.
