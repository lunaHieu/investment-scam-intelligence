# Project Direction Plan R3

Date: 2026-10-27  
Status: active amendment to Project Direction Plan R2  
Baseline commit at creation: `3e663a3f2b90a888f34ba7919fef64b47befdb1f`

R3 incorporates every unchanged objective, gate, denominator and safety rule
from `docs/project-direction-plan-r2.md`. It records only the verified change
below so that R2 remains an immutable historical planning snapshot.

## Verified amendment

The repository quality work in R2 section 7 items 1-2 and section 11 item 5 is
complete:

- exactly five historical pre-execution assertions were identified;
- all four hash-pinned historical test files remain byte-identical;
- five explicit post-execution replacements verify the consumed releases and
  registered output/QA hashes;
- the bounded current-suite runner refuses to start if an exclusion or its
  replacement is missing;
- the current full suite passes 1002/1002 tests;
- registry validation passes with 257 analysis registries.

The raw `unittest discover` command remains a historical lifecycle diagnostic.
It is expected to report the five superseded output-absence transitions on the
canonical machine. The active quality gate is:

```powershell
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v1
```

## Current executable order

1. Execute the one-row CDX metadata canary only after
   `2026-10-28T09:32:33.798697+07:00`.
2. In parallel, audit the 42 owner-accepted SEC EDGAR records against every G2
   admission field and prepare a bounded completion packet; do not fabricate
   human language review.
3. Advance evidence-sufficient Crimson primary review and retain `UNCERTAIN`
   where evidence is insufficient.
4. Prepare the first balanced `CONFIRMED` and Vietnamese acquisition wave.
5. Record a formal G0 scope decision before treating Image as optional in the
   final thesis claim.

No data, capture, label, split, validation, test, scoring, training or
deployment gate is opened by this amendment.
