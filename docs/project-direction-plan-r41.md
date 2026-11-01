# Project Direction Plan R41

Date: 2026-11-01

Baseline: `b6fab1762804726f290d222d72a72c61b483d855`.

## Completed in this update

### Stage 1 — PBC05/PBC08 offline closeout

The cross-version offline dossier is complete in
`docs/pbc05-pbc08-offline-closeout-v2.md` and its independent QA passed. It
reconciles the retained result snapshots without another request:

- PBC05 has three actual attempts; the exact historical exception cannot be
  recovered from retained data.
- PBC08 has two actual attempts; its earliest appearance was skipped after the
  PBC05 failure. The latest diagnostic identifies a forbidden-key guard but
  does not retain the key name, path, or value.
- PBC06/PBC07 remain provenance-only. No malware scan result is retained, so
  neither malware presence nor absence can be inferred.
- The same-release retry remains closed. No row was admitted, labeled, or made
  training-eligible.

### Stage 2 — Crimson owner confirmation and official-source evidence

The owner's confirmation is scoped to the 24 previously readiness-passed
primary recommendations. It does not certify the 15 follow-up tasks or any
independent second review.

The supplemental official-source workflow added 12 fact records across 11
pilot IDs, based on 11 distinct regulator pages or documents. It updates the
access-status snapshot for all 15 follow-up tasks. These are evidence notes;
no new human review decision was entered. The evidence and limits are in
`docs/crimson-official-source-followup-v2.md`.

- Three root-domain-only relationships remain unresolved:
  `me.tradextixcoins.com`, `www-stage.cedarfx.com`, and
  `affiliate.primexbt.com` are not assumed to share an operator with their
  listed root domains.
- The SC Malaysia announcement names PrimeXBT but does not name the candidate
  affiliate subdomain.
- Benefittrade and Banktrustcoin are visible only in FMA search-index results;
  their prior direct FMA access returned HTTP 429, so these snippets are not
  counted as directly reviewed evidence.
- Magnomic Yield Ltd appears in an official CONSOB search result, but the direct
  page access returned a bot challenge. No challenge was bypassed.
- The alternate CNMV result for Ai-MiningEx could not be opened. Its existing
  FCA fact record remains the directly reviewed source for that pilot.

No Crimson candidate host was accessed. The supplement retains no raw official
page files. All primary-review decisions for the 15 follow-up tasks remain
pending. No data rows or labels were created.

## Current review sequence

1. **Primary evidence review:** a human reviewer records the source check,
   identity relation, evidence assessment, reviewer, date, and notes. The 15
   follow-up tasks remain pending even where a new official fact is available.
2. **Blind second review:** a different human reviews the nine existing ready
   packets without primary or AI decisions. Zero of those reviews is complete.
   The 12 other double-review tasks still wait for primary review.
3. **Reconciliation:** perform only after both required reviews are recorded.
   Insufficient evidence, unclear identity, or disagreement remains
   `UNCERTAIN`.
4. **Admission:** do not admit a row to a usable dataset until source identity,
   evidence, required reviews, reconciliation, and owner acceptance are all
   recorded.

## Verification and safety state

The current source-supplement QA checks all 12 facts and 15 access-status rows,
including the three unresolved subdomain relationships and the closed review,
label, admission, and training gates. Current full-suite and registry results
are recorded in
`docs/reproducibility-current-state-v75.md` and
`registry/analyses/project_state_gap_ledger_v78.json`.

## Next actions

- Have the primary reviewer assess the newly recorded evidence and enter
  decisions through the existing human-review workflow.
- Obtain user-provided official copies or another permitted official access
  path for the FMA and CONSOB blockers; keep those rows `UNCERTAIN` until then.
- Assign the nine blind packets to a genuinely independent human reviewer.
- Reconcile only after the necessary review decisions are present.
- Keep PBC05/PBC08 closed unless a separately justified future release passes
  technical review and independent QA.
