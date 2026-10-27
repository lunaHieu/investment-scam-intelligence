# Reproducibility current state V37

V37 supersedes V36 for current navigation after the repository's artifact
lifecycle tests were made state-aware without editing any frozen historical
test, release, verifier or output.

The B5 continuation remains an immutable partial result and must not be rerun.
The one-row CDX metadata canary remains network-closed until
`2026-10-28T09:32:33.798697+07:00`; its release, target, request budget and
branch rules are unchanged.

The active repository quality command is now:

```powershell
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v1
```

It excludes exactly five obsolete pre-execution output-absence methods and
requires five explicit post-execution replacements. The current run passed
1002/1002 tests. Direct `unittest discover` remains a historical diagnostic,
not the post-execution quality gate. Registry validation passes with 257
analysis registries.

Project Direction Plan R3 is an amendment to R2 and leaves all research gates
unchanged. Fresh V1-Core remains 0/300 admitted groups; 42 owner-accepted
records remain conditional supply pending complete admission fields. No model
validation/test, scoring or training gate is open.
