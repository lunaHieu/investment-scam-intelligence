# Project Execution Sequence V1

Date: 2026-10-20
Status: frozen operational sequence from the current verified state

This sequence separates automated engineering work, AI-assisted preparation,
independent review, and actions that require a lawful external artifact or the
project owner's explicit final acceptance. A later phase may not silently skip
an earlier gate.

## Current position

- Historical text baseline train: 3,916 rows. Validation and test remain closed.
- Fresh V1-Core: 0/300 validated independent groups.
- SEC/IAPD V8: 113/115 availability rows resolved; 58 archived snapshots are
  available and frozen for capture; two rows remain quarantined.
- The 58-row plan contains 46 `DEVELOPMENT` and 12 `EXTERNAL_HOLDOUT` rows.
- The V5 capture release opens at `2026-10-21T14:19:54.213531+07:00`.
- Existing raw storage before this capture: 278 integrity-verified files.
- Verified Vietnamese supply and usable image assets: zero.

## Main gated sequence

1. **V9 availability retry and V5 capture execution**
   - Retry only the two quarantined availability rows.
   - Independently execute the immutable 58-row raw Wayback capture release.
   - Stop immediately on HTTP 429 and preserve any partial journal.
   - Meaning: obtain immutable candidate artifacts; availability is not a label.

2. **Independent capture byte/hash QA**
   - Recompute membership, order, file size and SHA-256 for every captured row.
   - A partial capture can only produce a separately frozen missing-row retry.
   - Meaning: establish that downstream work uses exactly the downloaded bytes.

3. **Exact-text extraction and regeneration QA**
   - Decode archived transport bytes and extract deterministic visible UTF-8.
   - Preserve below-minimum text but route it out of reviewable supply.
   - Independently regenerate every text byte.
   - Meaning: create the only artifact field that a future text model may use.

4. **Opened-cohort exclusion and disjoint grouping**
   - Compare against the 107 previously opened records.
   - Build transitive technical groups; exclude holdout members colliding with
     development and independently reproduce the complete analysis.
   - Meaning: prevent leakage and duplicate inflation before review.

5. **Manual group/clone review**
   - Confirm exclusions, merges and probable opened-clone relationships.
   - Keep all rows `UNCERTAIN`; create no binary label.
   - Meaning: resolve structural relationships automation cannot prove.

6. **Evidence-based primary artifact review**
   - Review captured content, identity linkage, task relevance, chronology,
     repurpose/parking and contradictions.
   - SEC/IAPD membership alone is insufficient for `LEGITIMATE`.
   - Meaning: create a recommendation, not ground truth.

7. **Blind independent second review**
   - Omit primary recommendations, assessments, rationale and summary.
   - Meaning: measure independent agreement without anchoring.

8. **Conservative reconciliation**
   - Any disagreement or insufficient evidence becomes `UNCERTAIN`.
   - Agreed `LEGITIMATE` remains a recommendation until owner acceptance.
   - Meaning: produce an auditable recommendation set without silent labels.

9. **Owner acceptance and corpus admission**
   - The owner explicitly accepts or rejects reconciled recommendations.
   - Re-run leakage, provenance, confidence and group-disjointness checks.
   - Meaning: this is the first point where a record may become label-eligible.

10. **Freeze development splits and model candidates**
    - Reach the required channel/language/group coverage before model selection.
    - Train only on development data, choose configuration only through frozen
      validation gates, then open the test partition once for final evaluation.
    - Meaning: model results become interpretable only after data gates pass.

## Parallel workstreams

### P1 — SEC/IAPD automation

Runs automatically at the frozen time gate. AI may execute, hash, validate,
prepare packets and perform explicitly authorized bounded review assistance.
It may not invent missing evidence, contact live candidate domains or create a
final label without the required review and acceptance chain.

### P2 — Crimson review handoff

Thirty-nine first-review tasks remain pending, one blind-second task is ready,
and twenty blind-second tasks wait for first review. AI may prepare evidence
summaries and structural QA. A reviewer identity must remain truthful; AI must
not impersonate an independent human reviewer.

### P3 — Manual source acquisition

- DFPI requires a lawful first-party artifact or explicit official export.
- SSC/HNX require an export or written reuse basis.
- These actions require user-supplied material or external permission. AI may
  validate, hash and register supplied artifacts after receipt.

### P4 — Research documentation

Can proceed at any time: methodology, provenance model, leakage controls,
review protocol, limitations, progress tables and reproducibility instructions.
Documentation must report candidate/reference counts separately from
training-ready rows.

## Immediate order from the current state

1. Keep the timed SEC/IAPD automation active.
2. Prepare a concise Crimson reviewer handoff without creating decisions.
3. Prepare a one-page user acquisition checklist for DFPI and SSC/HNX.
4. Update the research methodology/progress narrative from verified registries.
5. After the capture gate, resume the main gated sequence at capture QA.

Model retraining, validation opening, test opening, threshold selection and
deployment remain prohibited until fresh admitted groups satisfy their gates.
