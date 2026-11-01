# Reproducibility Current State V74

Date: 2026-11-01

Base commit: `925777714117cbcf2c446742f671213160a9d62a`

Current direction: `docs/project-direction-plan-r40.md`

## Crimson owner review progress

The user confirmed agreement with the existing Crimson decision. The
hash-pinned progress snapshot applies that confirmation narrowly to the 24
tasks already marked ready for primary review.

- Primary confirmations: 24.
- Single-review identity/evidence reconciliations: 16.
- Blind second-review tasks ready for a different human: 9.
- Double-review tasks still waiting for primary review: 12.
- Primary-review tasks still open behind official-reference follow-up: 15.
- Official source facts recorded: 6 rows; all 15 follow-up tasks remain open.
- Model labels, data admission and training eligibility: 0.

The reviewer handoff is at
`D:\nckh 2026-2027\ISI_Data\derived\crimson_primary_review_readiness_v1\blind_second_review_handoff_v2.jsonl`.
It contains no AI or primary-review decisions. A genuinely independent human
must still complete those reviews. The owner-progress registry and its offline
QA pin every output hash.

The six official pages reviewed were the SFC BitForex warning, FCA warnings for
Ai-MiningEx, Chainstackinvest.com and OPENTRADING PLATFORM, the AMF Québec
PrimeWealth warning, and the SEC Trade Xtix Coins public alert. Their compact
facts and interpretation limits are recorded in the derived evidence JSONL.
Raw page files were not retained; the 21 remaining URL occurrences keep their
prior blocked/unconfirmed statuses and were not retried. No candidate domain
was accessed.

The one-shot materializer wrote all outputs and its registry, then returned
`UnicodeEncodeError` while printing Vietnamese JSON to the Windows console.
The immutable outputs were not regenerated. The separate verifier checked
their hashes, record counts, blind-field boundary, and closed label/training
gates with status `PASS_OWNER_PROGRESS_ARTIFACTS_AND_OPEN_GATES_VERIFIED`.

## PBC05/PBC08 offline closeout

`docs/pbc05-pbc08-offline-closeout-v2.md` reconciles three result snapshots
against their hashes. PBC05 has three actual attempts; the two instrumented
attempts have the same PDF response hash but different stderr hashes, and the
exact failure remains unrecoverable. PBC08 has two actual attempts; the earliest
result skipped it after PBC05 failed. The latest diagnostic confirms the
forbidden-key guard but not the key name. PBC06/PBC07 are metadata/documentation
provenance only. No malware scan result is available, so malware presence or
absence cannot be inferred.

The closeout QA status is `PASS_RESULT_HISTORY_RECONCILED_NO_CAUSE_OVERCLAIMED`.
It authorizes no retry, acquisition, data admission, labeling, or training.

## Verification

Commands run with the project virtual environment:

```powershell
.venv\Scripts\python.exe -m scripts.validate_registry
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10
.venv\Scripts\python.exe -m scripts.verify_crimson_owner_review_progress_v1
.venv\Scripts\python.exe -m scripts.verify_pbc05_pbc08_offline_closeout_v2
```

Recorded results:

- Registry validation: 414 analysis registries passed after writing the V74
  reproducibility and V77 state-ledger snapshots.
- Current full suite V10: 1,197 passed, 0 failed.
- Crimson progress QA: pass; 0 blind-field leaks, 0 labels, 0 eligible rows.
- PBC offline closeout QA: pass; no new source requests.

## Current hard limits

- Do not retry the exhausted PBC release. A different release requires a new
  technical package, independent QA, and scoped owner authorization.
- Do not complete blind second review with an AI or the same primary reviewer.
- Do not infer a scam/legitimate label from regulator warnings, SEC/IAPD
  identity evidence, source availability, or the PBC parser outcome.
- Do not admit any row until source, evidence, required reviews, reconciliation
  and owner acceptance are recorded.
- Do not open model validation/test data or train/score a model in this review
  workflow.
