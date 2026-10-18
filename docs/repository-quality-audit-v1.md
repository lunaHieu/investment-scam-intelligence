# Repository Quality Audit V1

Date: 2026-10-18  
Audit base: `7e481e3`  
Status: `PASS_WITH_TRACKED_PORTABILITY_AND_RESEARCH_READINESS_DEBT`

## Executive assessment

The repository is internally consistent on the canonical research machine,
cross-platform checkout behavior is now controlled, and an automated public CI
gate runs on Windows and Ubuntu with Python 3.10 and 3.11. This engineering
status does **not** mean that the research dataset is complete or that a model
is ready for deployment.

## Verified evidence

- The local `main` branch matched `origin/main` and the working tree was clean
  before this audit was finalized.
- The complete local test suite passed: 718 tests on the project Python 3.10
  venv.
- GitHub Actions run 9 passed all four operating-system/Python combinations.
- A fresh-checkout regression test verifies Git line-ending behavior with
  `core.autocrlf=true` and preserves the one historically hash-pinned Mendeley
  manifest byte-for-byte.
- Repository-only CI compiles `scripts/`, `src/`, and `tests/`, checks the
  current-state pointer and dependency contract, and runs a focused safety
  suite including the cross-platform V7 capture-plan/release round trip.
- The registered raw provenance audit remains complete for the existing raw
  corpus: 278 files, 1,640,058,635 bytes, 278 hash-pinned files, zero existing
  raw hash mismatches, and zero parse failures.
- Two historical missing claim targets remain recorded; they do not represent
  missing files in the current 278-file raw corpus.

## Improvements completed in this audit

1. Added `.gitattributes` to make tracked text bytes stable across platforms.
2. Preserved the exact historical byte representation of the one Mendeley
   manifest whose Windows bytes are already referenced by frozen hashes.
3. Added `CURRENT_STATE.md` as a mutable navigation entry without rewriting
   historical reports.
4. Added a four-job public CI matrix for Windows/Ubuntu and Python 3.10/3.11.
5. Added direct dependency groups for baseline and embedding workflows and an
   AST-based test that rejects undeclared third-party imports.
6. Added a canonical cross-platform capture fixture after proving that the
   older frozen fixture used a noncanonical Windows temporary-path spelling.
   Frozen scientific artifacts were not rewritten.

## Tracked engineering debt

- A full suite run from an arbitrary clone still contains six historical,
  location-bound failures: five module-preflight checks freeze the original
  repository path, and one legacy review stores the original protocol path.
  These frozen artifacts remain valid on the canonical machine but are not
  portable. They should be superseded by new path-neutral versions, not edited
  in place.
- Twenty-four Python/JavaScript files still contain the canonical absolute data
  root (`D:\nckh 2026-2027\ISI_Data`): 9 scripts and 15 tests. New code should
  not increase this inventory.
- The repository has no enforced coverage threshold, static type gate, or
  linter gate yet.
- The large number of versioned scripts and tests is valuable for audit history
  but raises maintenance cost. Shared primitives should be extracted only in
  new versions so frozen hash chains remain intact.

## Research-readiness boundary

The current project ledger still reports:

- SEC/IAPD: 115 planned, 107 resolved, 52 available, 55 unavailable, and 8
  unresolved; V7 remains controlled by its timed gate.
- Historical baseline train rows: 3,916.
- Fresh V1-Core validated groups: 0 of 300 required.
- Crimson: 39 first-review items, 1 blind-second-review-ready item, 20 waiting
  items, and 15 official-reference follow-ups.
- Verified Vietnamese supply: 0; usable image assets: 0.

Therefore training, validation/test opening, model scoring, deployment, live
candidate-domain access, and premature labeling remain closed exactly as stated
in the current ledger.

## Recommended next quality work

1. Allow the predeclared V7 timed gate to run under its existing safety
   contract; do not bypass its cooldown.
2. Add a path-portability debt registry that freezes the current 24-file
   allowlist and rejects any increase.
3. Create new path-neutral module-preflight and legacy-review verifier versions
   while retaining the historical versions unchanged.
4. Establish a coverage baseline before selecting a minimum threshold, then add
   lint/type gates incrementally to avoid mass rewrites of frozen scripts.
