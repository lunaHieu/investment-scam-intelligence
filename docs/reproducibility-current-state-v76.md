# Reproducibility Current State V76

Date: 2026-11-02

Baseline: `17c2ebf1fec504985f9a7a52314be055d45615fb`.

Current direction: `docs/project-direction-plan-r42.md`.
Current gap ledger: `registry/analyses/project_state_gap_ledger_v79.json`.

## Crimson CONSOB official-source addendum V3

The V3 frozen workflow adds one directly read official source document for
`PILOT_CRIMSON_REF_016`:

- CONSOB, “Abusive financial services: Consob blacks out 7 abusive websites,”
  20 June 2025.
- The English-language PDF names Magnomic Yield Ltd and the exact host
  `magnomicyieldltd.com` among sites ordered blocked.
- The different source URL was read; the previously challenged CONSOB
  warnings/latests URL was neither retried nor bypassed.
- The raw PDF was not retained. The record pins the official URL and a bounded
  fact summary. This remains an official warning/measure, not a court finding
  or label for a message.

Independent QA is
`registry/analyses/crimson_official_source_followup_v3_qa.json`; the fact and
access-status outputs are outside Git in
`D:\nckh 2026-2027\ISI_Data\derived\crimson_primary_review_readiness_v1\`.
The source fact improves the evidence available for primary review, but the
human decision remains pending. No label or data admission was made.

An AI-assisted review brief for this one task is at
`reports/crimson_external_reference_review_pilot_v1/PILOT_CRIMSON_REF_016_review_brief_v1.md`
and its JSON companion. It proposes `SAME_ENTITY` plus `WARNING_RELEVANT`, but
requires human confirmation and is not written to the decision log.

The offline AI-assisted draft for all 15 follow-up cases is
`docs/crimson-primary-evidence-assessment-draft-v1.md`. It is not a decision
artifact and must remain excluded from blind second-review packets.

The separate reviewer instructions for the nine ready blind packets are in
`docs/crimson-blind-second-review-handoff-v2.md`. Offline integrity checks
matched the frozen nine-row handoff hash and confirmed the listed primary/AI
fields are omitted. No independent human has been assigned or recorded.

## Crimson review state

- Earlier owner-confirmed recommendations: 24.
- Identity/evidence-level single-review reconciliations: 16.
- Ready blind second-review packets: 9; completed: 0.
- Double-review tasks waiting on primary review: 12.
- Official-reference primary follow-ups: 15; completed: 0.
- Direct official source facts across pinned V1/V2/V3 supplements: 19 records
  across 18 distinct directly read pages/documents.
- FMA Benefittrade and Banktrustcoin artifacts remain unresolved. The FMA
  search result is not counted as a direct source read.

## PBC05/PBC08

The V2 offline closeout remains complete and immutable. PBC05 has three
recorded attempts and the exact historical exception is unrecoverable from
retained files. PBC08 has two actual attempts; the latest diagnostic found a
forbidden-key guard but did not retain the key/path/value. No malware scan
result exists. Neither row was admitted or labeled.

## Verification performed

```powershell
.venv\Scripts\python.exe -m scripts.materialize_crimson_official_source_followup_v3
.venv\Scripts\python.exe -m scripts.verify_crimson_official_source_followup_v3
.venv\Scripts\python.exe -m unittest discover -s tests -p test_crimson_official_source_followup_v3.py
.venv\Scripts\python.exe -m scripts.validate_registry
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10
```

Results before writing the V76/V79 navigation snapshots:

- V3 independent QA: `PASS_ALTERNATE_OFFICIAL_FACT_PINNED_PRIMARY_REVIEW_STILL_PENDING`.
- Focused V3 tests: 3 passed.
- Registry validation: 420 analysis registries passed. The V76 and V79
  navigation registries bring the final registered count to 422.
- Current full test suite V10: 1,206 passed, 0 failed.
- Candidate-host access: 0. Previously blocked URL retries: 0. Labels and
  admitted rows: 0. Training-eligible: 0.

The current full suite includes the V3 supplement tests and the V76/V79
navigation snapshot tests. The final registry validation runs after the
V76/V79 registries are written.

## Active gates

1. Human primary review of the 15 official-reference follow-ups.
2. A genuinely independent human's blind review of the 9 ready packets and
   later eligible packets.
3. Explicit reconciliation after those reviews.
4. Owner acceptance before any admission or label materialization.
5. Official source copies or an authorized access route for the two FMA rows;
   lawful artifacts/exports or reuse basis for DFPI and SSC/HNX.

Insufficient evidence, unresolved subdomain identity, and disagreement remain
`UNCERTAIN`. Validation/test access, scoring, and training remain closed.
