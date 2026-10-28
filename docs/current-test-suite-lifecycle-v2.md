# Current Test Suite Lifecycle V2

V2 preserves the five historical transitions in V1 and adds exactly one new
post-execution transition: the ready-channel CDX canary release now has an
immutable final report and independent QA, so its historical output-absence
assertion is superseded by a hash-bound post-execution check.

The current quality gate is:

```powershell
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v2
```

The runner refuses to start if any of the six historical methods or six
explicit replacements is missing. No frozen historical test file is edited.
