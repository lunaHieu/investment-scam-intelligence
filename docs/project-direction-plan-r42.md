# Project Direction Plan R42

Date: 2026-11-02

Baseline: `17c2ebf1fec504985f9a7a52314be055d45615fb`.

## Completed in this update

### Crimson official-source follow-up — alternate CONSOB artifact

An alternate English-language CONSOB press-release PDF was directly read for
`PILOT_CRIMSON_REF_016` after the previously challenged CONSOB page was left
untouched. The release, dated 20 June 2025, names Magnomic Yield Ltd and the
exact website `magnomicyieldltd.com` among seven sites CONSOB ordered blocked.
The source fact and access update are frozen in the V3 addendum and independently
verified. No raw PDF was retained.

This closes the direct-source-access gap for that one task, but it does not
complete its human primary review. It does not establish the contents of any
particular message, create a label, or admit a row. The prior blocked URL was
not retried; no candidate host was accessed.

### Verification

- V3 official-source addendum: independent QA passed for one exact-host fact.
- Focused tests: 3 passed.
- Registry validation before current navigation snapshots: 420 analysis
  registries passed; after adding this plan's V76/V79 navigation registries,
  the final count is recorded in the V79 ledger.
- Current full suite V10: 1,206 passed, 0 failed.
- Crimson primary decisions completed by this update: 0.
- Labels, admitted rows, or training-eligible records created: 0.

### Primary-review preparation — Magnomic

An AI-assisted review brief is now prepared for `PILOT_CRIMSON_REF_016` in
`reports/crimson_external_reference_review_pilot_v1/`. It proposes
`SAME_ENTITY` plus `WARNING_RELEVANT`, based on the directly read exact-host
CONSOB release. It remains a draft: no human decision was recorded, no label
was created, and the brief preserves the second-review requirement.

An offline AI-assisted evidence draft now covers all 15 official-reference
follow-ups in frozen review order. It keeps the three root/name-only cases and
two FMA access blockers `UNCLEAR`/`INSUFFICIENT_EVIDENCE`; the other ten are
proposed only as exact-host warning or registration relationships. All human
primary tasks remain pending. The draft is
`docs/crimson-primary-evidence-assessment-draft-v1.md` and must stay out of
blind-review packets.

The nine already-ready blind second-review packets were rechecked offline:
their pinned hash matches, all nine are unique and ready, and the required
primary/AI fields are omitted. A clean reviewer handoff is now documented in
`docs/crimson-blind-second-review-handoff-v2.md`; no reviewer was contacted or
assigned.

## Current position

- Crimson: 24 earlier recommendations were explicitly owner-confirmed; 16
  identity-level single reviews remain non-label recommendations. All 15
  official-reference follow-up primary reviews remain pending. Direct facts
  now include the CONSOB V3 fact for Magnomic; the FMA rows Benefittrade and
  Banktrustcoin still lack a directly reviewed artifact.
- Blind review: 9 packets are ready for an independent second human reviewer;
  0 are complete. Another 12 tasks still wait for primary review.
- PBC05/PBC08: offline closeout is complete and immutable. Exact historical
  causes remain partly unrecoverable, and no malware scan result exists.
- Data admission, label materialization, validation/test access, model scoring,
  and training remain closed for these workstreams.

## Next actions

1. **Primary evidence review:** the reviewer records a truthful identity and
   evidence decision for the 15 follow-up tasks, using only the frozen official
   facts and treating the AI draft as a proposal. For Magnomic, assess the
   exact-host Consob release and its limits.
   For root-only/name-only matches or insufficient evidence, retain
   `UNCERTAIN`. The Magnomic AI-assisted brief is prepared for human
   confirmation; do not treat its suggestion as a decision.
2. **Source-access work in parallel:** request official copies or authorized
   direct access for the FMA evidence concerning Benefittrade and Banktrustcoin.
   Do not repeat the rate-limited FMA URL. A search result is a lead, not a
   directly reviewed source artifact.
3. **Independent blind review:** assign the nine ready packets to a different
   human reviewer who cannot see primary decisions or AI suggestions. The
   assistant must not act as or impersonate this reviewer. Use the V2 handoff
   without sharing the AI assessment draft.
4. **Additional source supply:** DFPI needs a lawful first-party artifact or
   official export; SSC/HNX need an export or documented reuse basis. Validate
   and register supplied materials without changing their source labels.
5. **Reconciliation and owner acceptance:** reconcile only after required
   reviews. Disagreement, unclear identity, and insufficient evidence remain
   `UNCERTAIN`. Keep records out of usable data until source, reviews,
   reconciliation, and owner acceptance are complete.

No archive request, capture, model operation, or PBC retry is part of this
update. Use the V79 gap ledger and V76 reproducibility state as current
navigation.
