# Reproducibility Current State V75

Date: 2026-11-01

Baseline: `b6fab1762804726f290d222d72a72c61b483d855`.

Current direction: `docs/project-direction-plan-r41.md`.

## Crimson official-source supplement V2

The frozen workflow config is `configs/crimson_official_source_followup_v2.json`.
It defines 12 facts across 11 pilot IDs, and a new access-status row for each
of the 15 open official-reference follow-ups. The facts are stored outside Git
in `D:\nckh 2026-2027\ISI_Data\derived\crimson_primary_review_readiness_v1\`.
No raw source pages are retained. The exact output/config/implementation hashes
are pinned in `registry/analyses/crimson_official_source_followup_v2.json`; its
independent QA is `registry/analyses/crimson_official_source_followup_v2_qa.json`.

- Supplement QA: `PASS_OFFICIAL_FACTS_PINNED_REVIEW_AND_ADMISSION_STILL_CLOSED`.
- New fact rows: 12; distinct pilot IDs: 11; directly read official pages or
  documents: 11.
- Status rows: 15. Every primary-review status remains pending.
- Three root-only relations and one name-only record remain unresolved.
- Search-index-only FMA/CONSOB results are not counted as direct evidence;
  the prior FMA rate limits and CONSOB challenge remain documented.
- Candidate hosts accessed: 0. Labels, admitted rows, and training-eligible
  records: 0.

## Crimson review state

- Owner confirmation: 24 existing readiness-passed primary recommendations.
- Identity/evidence-level single-review reconciliations: 16.
- Blind second-review handoffs ready: 9; completed: 0.
- Double-review tasks waiting on primary review: 12.
- Primary follow-up tasks still pending: 15.
- Total source fact records across owner-progress V1 and official-source V2:
  18; distinct direct official pages/documents across these snapshots: 17.
- Data admission and label materialization remain closed.

The owner's confirmation applies only to the original 24 recommendations. It
does not decide the newly collected facts, complete the 15 pending primary
reviews, or replace a genuinely independent second reviewer.

## PBC05/PBC08 offline dossier

`docs/pbc05-pbc08-offline-closeout-v2.md` and its verifier remain pinned by the
prior PBC closeout registry. PBC05 has three attempts, but its exact cause is
unrecoverable. PBC08 has two attempts; the earliest result skipped it, while the
latest diagnostic found a forbidden-key guard but not the key name/path/value.
No malware scan result exists, so malware presence or absence cannot be
inferred. PBC06/PBC07 remain provenance-only. No PBC rows were admitted.

## Verification

Commands run with the project virtual environment:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_crimson_official_source_followup_v2.py
.venv\Scripts\python.exe -m scripts.verify_crimson_official_source_followup_v2
.venv\Scripts\python.exe -m scripts.validate_registry
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10
```

Results after the new analysis and QA registries were added:

- Focused supplement tests: 3 passed.
- Registry validation before the navigation snapshots: 416 analysis registries
  passed; the final validation count is recorded in the V78 ledger after adding
  the current reproducibility and gap-ledger registries.
- Current full suite V10: 1,200 passed, 0 failed.
- Supplement independent QA: pass, with no source-page downloads, candidate
  domain access, label changes, data admission, or model operations.

## Remaining gates

1. Human primary review of the 15 official-reference follow-ups.
2. Independent blind review of the nine ready handoffs and later review tasks
   that require a second reviewer.
3. Explicit reconciliation after all required human decisions are recorded.
4. Source/evidence/review/owner acceptance before any data admission or label
   materialization.

Keep `UNCERTAIN` for insufficient evidence, root/name-only mismatches, and
review disagreement. Do not use the PBC result or regulator listing by itself
as a model label.
