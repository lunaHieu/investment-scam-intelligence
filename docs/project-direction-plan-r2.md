# Project Direction Plan R2

Date: 2026-10-26  
Status: active planning and progress-tracking guide  
Baseline commit at creation: `ffdac06fc089e9e5ef822219d8ebfbadc1b2a13d`

This guide translates the original ISI V1 roadmap into a bounded execution
plan from the current verified state. It does not overwrite historical
snapshots, alter frozen cohort identities, open a network or model gate, or
change an existing release contract by itself.

## 1. Direction

The recommended primary deliverable is **Thesis Core R2**:

- evidence-backed fresh text corpus;
- text, URL and Financial Claims models/features;
- grouped and source-aware evaluation;
- calibrated probability, risk tiers and an explicit `UNCERTAIN` route;
- inspectable evidence and XAI;
- untouched external evaluation;
- reproducible API or demonstration.

Basic image processing and multimodal late fusion remain an extension that
should be activated only after a compatible image corpus exists. Behavioral
intelligence, graph analysis, social APIs and agent orchestration remain later
extensions. This prioritization is a planning recommendation; changing the
original locked Core scope requires a separately recorded scope decision.

## 2. Current baseline

| Axis | Verified current state | Interpretation |
| --- | ---: | --- |
| Repository | clean and synchronized at plan creation | Engineering work is reproducible on the canonical machine |
| Existing raw storage | 278/278 files hash-verified; 1,640,058,635 bytes | Complete integrity coverage of stored raw, not complete acquisition |
| Historical development reference | 3,916 train rows / 3,783 groups | Internal baseline only; not fresh V1-Core credit |
| Fresh V1-Core admitted | 0/300 groups | Formal corpus release is not ready |
| Conditional accepted supply | 42/300 groups | All 42 are SEC EDGAR-linked `LEGITIMATE`; conditional gap is 258 |
| SEC/IAPD review population | 56 reviewable; 42 accepted; 14 `UNCERTAIN` | The end-to-end review chain has been demonstrated |
| Crimson primary review | 1/40 complete | Manual evidence review remains a material backlog |
| Verified Vietnamese supply | 0/16 minimum | Language coverage is a blocking corpus gap |
| Compatible image assets | 0 | Multimodal modeling is not ready |
| Text reference | word TF-IDF logistic OOF Macro-F1 0.721038 | Retain as reference; not deployment-ready |
| Active acquisition | exact-69 continuation stopped on its first HTTP 429; CDX canary frozen | Archive metadata canary gate opens 2026-10-28 09:32:33 +07:00 |

The executive completion estimate is approximately 35% for the complete
research deliverable, while research-engineering foundations are approximately
60-65% complete. Progress must continue to be reported as a vector rather than
as only one percentage.

## 3. Definition of Done

Thesis Core R2 is complete only when all of the following are true:

1. The dataset has evidence-backed labels, provenance and lawful reuse records.
2. Development and external holdout are group-, campaign-, entity- and
   near-duplicate-disjoint.
3. Model selection uses development data only.
4. Validation selects one frozen configuration and threshold.
5. External holdout is opened once after configuration freeze.
6. The final system returns calibrated probability, risk tier, uncertainty,
   evidence and a versioned explanation.
7. Dataset card, model card, limitations, reproducibility instructions and a
   demonstrable inference interface are complete.

## 4. Execution stages and gates

### G0 - Rebaseline the deliverable

**Meaning:** remove ambiguity between the original high-volume multimodal
roadmap and the bounded current corpus contract.

Actions:

1. Record Thesis Core, Multimodal Extension and Research Extension explicitly.
2. Freeze the active research questions and required ablations.
3. Decide whether image remains a mandatory Core dependency or becomes a
   declared extension.
4. Preserve the existing 300-group V1-Core denominator unless a formal scope
   amendment is supported by acquisition evidence.

Exit criteria:

- one authoritative scope statement exists;
- every workstream maps to a required deliverable or is marked optional;
- no historical release or result is rewritten.

### G1 - Close active acquisition branches finitely

**Meaning:** obtain useful outcomes without allowing repeated service failures
to stall the entire project.

Actions:

1. Execute the exact-69 B5 continuation at its verified gate.
2. Account for every row as available, unavailable, endpoint error or
   quarantined.
3. If complete, prepare an all-and-only-resolved capture plan.
4. If partial, permit only the separately frozen one-row metadata canary.
5. If the canary receives HTTP 429, close the archive-provider branch and move
   the remaining population to non-archive source assessment.

Operating rules:

- a row failure quarantines the row, not the cohort;
- a source failure does not block independent workstreams;
- cooldown is based on response evidence and the retry policy, not a universal
  24-hour delay;
- every row and source has a finite retry budget;
- availability never creates a label.

Exit criteria:

- every planned row has an immutable outcome;
- no unreconciled partial journal remains;
- the next action is capture, alternative source assessment or quarantine;
- no unbounded retry loop remains.

### G2 - Make the 42 accepted records contract-complete

**Meaning:** convert existing review effort into usable supply before acquiring
more records of the same channel.

Actions:

1. Complete channel, language, evidence class, group identity, exclusion,
   cohort, capture provenance, confidence and release-eligibility fields.
2. Perform human language review of visible text.
3. Recompute cross-cohort duplicates and transitive groups.
4. Check DEVELOPMENT versus EXTERNAL_HOLDOUT collision.
5. Route insufficient or contradictory records to `UNCERTAIN` or exclusion.
6. Produce contract-complete packets without calling them a partial balanced
   release.

Exit criteria:

- all 42 records are contract-complete or explicitly routed out;
- language credit is human-verified;
- zero development/holdout collision;
- every retained decision has a traceable evidence chain.

### G3 - Build balanced V1-Core supply in bounded waves

**Meaning:** address the main project bottleneck: high-quality, balanced and
disjoint ground truth.

Target matrix:

| Channel | Development | External holdout | Total |
| --- | ---: | ---: | ---: |
| `CONFIRMED` regulator-linked | 60 | 15 | 75 |
| `CONFIRMED` CFTC RED-linked | 60 | 15 | 75 |
| `LEGITIMATE` IAPD-linked | 60 | 15 | 75 |
| `LEGITIMATE` SEC EDGAR-linked | 60 | 15 | 75 |
| **Total** | **240** | **60** | **300** |

Language overlay:

- at least 30 human-reviewed non-English groups;
- at least 16 human-reviewed Vietnamese groups;
- language credit must exist in both labels and both cohorts as required by the
  frozen contract.

Acquisition priority:

1. `CONFIRMED` regulator-linked;
2. `CONFIRMED` CFTC RED-linked;
3. `LEGITIMATE` IAPD-linked;
4. the remaining SEC EDGAR-linked legitimate gap;
5. Vietnamese and other non-English supply inside every wave, not at the end.

Wave size should normally be 25-50 groups. Each wave follows:

`permission/reuse -> candidate manifest -> immutable capture -> byte/hash QA ->
exact text -> opened-overlap exclusion -> transitive grouping -> primary review
-> blind second review -> reconciliation -> owner acceptance -> admission QA`

Crimson runs in parallel:

- finish the remaining 39 primary reviews;
- send only evidence-sufficient rows to blind second review;
- keep anomaly scores and domain membership out of ground truth;
- route official-reference gaps into a separate evidence queue;
- preserve `UNCERTAIN` when evidence is insufficient.

Exit criteria:

- 300 contract-complete disjoint groups, or a formal denominator amendment
  supported by documented acquisition evidence;
- 150 `CONFIRMED` and 150 `LEGITIMATE` groups;
- 240 DEVELOPMENT and 60 untouched EXTERNAL_HOLDOUT groups;
- required language coverage;
- zero cross-split clone or identity collision.

### G4 - Freeze Dataset V1

**Meaning:** create one immutable research object for model development and
final evaluation.

Required artifacts:

- dataset manifest;
- group and split manifests;
- provenance and license/reuse manifests;
- exclusion manifest;
- dataset card and label guideline;
- review agreement and reconciliation report;
- known-limitations statement.

Split policy:

- DEVELOPMENT supports grouped OOF and configuration selection;
- EXTERNAL_HOLDOUT remains unopened until model/configuration freeze;
- validation is derived from DEVELOPMENT with group/source constraints;
- holdout rows are never moved to training to repair balance.

Exit criteria:

- hashes and membership independently verify;
- no unresolved identity or split collision;
- full current test suite passes without undocumented stateful failures;
- the dataset card explains source, label semantics, intended use and limits.

### G5 - Run bounded model development

**Meaning:** test explicit hypotheses instead of searching models indefinitely.

Authorized comparison after Dataset V1 freeze:

1. word TF-IDF plus regularized logistic regression;
2. one predeclared multilingual encoder revision;
3. URL structured model;
4. Financial Claims feature model;
5. small late fusion over text, URL and Claims;
6. image/fusion only on a sufficiently sized complete-modality subset.

Experiment order:

- E1 text baseline;
- E2 multilingual text challenger;
- E3 URL-only;
- E4 Claims-only;
- E5 text plus URL;
- E6 text plus Claims;
- E7 text plus URL plus Claims;
- E8 image and multimodal fusion if the image gate opens.

Required metrics:

- Macro-F1 and per-label recall/F1;
- worst-source and worst-channel F1;
- Vietnamese and non-English F1;
- Brier score and expected calibration error;
- source predictability;
- abstention coverage and accuracy;
- error distribution by subtype.

Exit criteria:

- one configuration selected from DEVELOPMENT/validation only;
- configuration, seed and threshold are frozen;
- no external holdout result influenced model selection;
- model card and train-only error analysis are complete.

### G6 - Add calibration, risk and evidence-aware XAI

**Meaning:** turn a classifier into an auditable decision-support system.

Actions:

1. Calibrate the frozen score on validation.
2. Select risk tiers from validation evidence.
3. Implement `UNCERTAIN`/abstention for low confidence, contradictory evidence,
   out-of-distribution input and critical missing modalities.
4. Separate model-feature evidence, provenance evidence and ground-truth
   evidence.
5. Produce sparse feature, claim, URL and provenance explanations.
6. Permit an AI agent to summarize only verified structured evidence; it may
   not invent a legal conclusion, regulator action or ground truth.

Exit criteria:

- calibration improves the declared validation metric;
- threshold selection is reproducible;
- explanations cite only registered evidence;
- hallucination, leakage and missing-evidence tests pass.

### G7 - Run one-time external evaluation

**Meaning:** measure generalization without turning the final test into another
development set.

Actions:

1. Freeze model, preprocessing, thresholds and output schema.
2. Open external holdout once.
3. Report overall, per-source, per-channel, per-language, hard-negative,
   abstention and calibration results.
4. Perform descriptive error analysis without retuning on the holdout.
5. State clearly what the system can and cannot support.

Exit criteria:

- final result table, confusion matrix, calibration plot and error taxonomy;
- no post-holdout configuration change;
- externally observed weaknesses are retained as limitations or future work.

### G8 - Integrate, demonstrate and freeze the thesis package

**Meaning:** convert research artifacts into a reproducible deliverable.

Minimum interface:

- input: text, URL and optional image;
- output: probability, risk tier, predicted class, uncertainty/abstention,
  structured claims, evidence and model/version metadata.

Required documentation:

- problem definition and taxonomy;
- data and ground-truth methodology;
- leakage controls;
- baselines and ablations;
- calibration, risk and XAI;
- external evaluation;
- ethical, legal and operational limitations;
- reproducibility appendix;
- demo and execution guide.

Exit criteria:

- a clean checkout can verify manifests and reproduce the main result tables;
- the frozen artifact can run the demo on the supported environment;
- dataset card, model card and thesis evidence tables agree.

## 5. Parallel workstreams

| Workstream | Immediate objective | May run while network gates are closed |
| --- | --- | --- |
| A - Acquisition | finish B5 and acquire balanced channel supply | yes, for offline preparation and alternative-source assessment |
| B - Review and admission | complete 42 accepted records and Crimson review | yes |
| C - Engineering quality | repair stateful tests and reduce version/tooling debt | yes |
| D - Research documentation | methodology, cards, limitations and progress tables | yes |
| E - Modeling | preserve baseline and prepare frozen protocols | yes, but no new scoring/training before its gate |
| F - Multimodal | identify lawful compatible image supply | yes, but it cannot block Thesis Core preparation |

## 6. AI and human responsibilities

AI may:

- execute frozen acquisition releases;
- verify bytes and hashes;
- extract exact text;
- propose duplicate/group relationships;
- screen language and prepare review packets;
- summarize cited evidence;
- run tests, permitted experiments and consistency audits;
- maintain progress and capacity ledgers.

Human responsibility remains required for:

- access or reuse permission when a source requires it;
- independent evidence judgment;
- a genuinely blind second review;
- reconciliation of disagreement;
- owner acceptance;
- material changes to scope, denominators or research claims.

AI-assisted review must never be presented as two independent human reviewers.

## 7. Engineering quality actions

1. Separate pure unit tests from pre-execution and post-execution artifact
   tests.
2. Replace tests that always require output absence with explicit state-aware
   fixtures.
3. Keep historical artifacts immutable, but supersede stale navigation files.
4. Avoid a new script/version when the contract has not materially changed.
5. Consolidate shared primitives only in new code paths so frozen hashes remain
   valid.
6. Require a green focused suite for the active branch and a green full suite
   before a material release.

## 8. Anti-delay rules

1. A failed row does not block the cohort.
2. A failed source does not block independent workstreams.
3. No endpoint receives an unlimited retry budget.
4. No universal 24-hour cooldown is applied without supporting evidence.
5. No new model is tried without a written hypothesis and promotion rule.
6. Validation and external holdout are not exploratory datasets.
7. Image and Behavior do not block the recommended Thesis Core unless scope is
   explicitly changed back.
8. Candidate/reference/availability counts are never reported as admitted
   training groups.
9. Every material week must produce an artifact consumed by a later gate, not
   only more tooling.
10. Historical snapshots remain immutable; current navigation is updated
    instead.

## 9. Proposed schedule

| Week | Main objective | Expected gate |
| --- | --- | --- |
| 1 | record R2 scope, finish B5, repair state handling | G0-G1 |
| 2 | complete the 42 accepted packets and advance Crimson review | G2 |
| 3-5 | acquire and review `CONFIRMED`, IAPD and Vietnamese waves | G3 in progress |
| 6 | close capacity gaps, grouping and reconciliation | G3 |
| 7 | freeze Dataset V1 and documentation | G4 |
| 8-9 | text, URL, Claims and controlled fusion experiments | G5 |
| 10 | calibration, risk, abstention and XAI | G6 |
| 11 | one-time external evaluation | G7 |
| 12 | API/demo and Thesis Core freeze | G8 |
| 13-16 | image/multimodal extension if its data gate opens | optional extension |

This schedule is dependency-based. A blocked network branch does not pause
review, engineering quality, documentation or offline preparation.

## 10. Progress dashboard

Update this table only from independently verified artifacts.

| Milestone | Baseline on 2026-10-26 | Target | Status |
| --- | ---: | ---: | --- |
| B5 continuation accounted | final partial report: 1 request, 69 unresolved; row 001 remains quarantined | finite branch outcome | continuation closed; CDX canary pending |
| Conditional accepted records made contract-complete | 0/42 | 42/42 | pending |
| Fresh V1-Core admitted groups | 0 | 300 | blocked by supply/admission |
| `CONFIRMED` groups | 0 | 150 | critical gap |
| `LEGITIMATE` conditional supply | 42 | 150 | partial, one channel only |
| Verified Vietnamese groups | 0 | at least 16 | critical gap |
| Crimson primary reviews | 1 | 40 | in progress |
| Dataset V1 freeze | no | yes | closed |
| Final model configuration | no | one frozen winner | closed |
| External evaluation | no | one-time complete | closed |
| API/demo | no | reproducible | not started |

## 11. Next executable order

1. Execute and independently verify the one-row CDX metadata canary at or after
   `2026-10-28T09:32:33.798697+07:00`.
2. In parallel, complete admission and language fields for the 42 accepted
   SEC EDGAR records.
3. Advance Crimson primary review without converting unsupported recommendations
   into labels.
4. Prepare the first balanced `CONFIRMED` acquisition wave and a Vietnamese
   overlay.
5. Repair the five historical state-transition test failures by separating
   pre-execution and post-execution expectations.
6. Record the formal G0 scope decision before treating Image as optional in a
   final thesis claim.

