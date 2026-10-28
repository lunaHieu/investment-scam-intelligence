# Current Test Suite Lifecycle V3

V3 preserves the six historical transitions in V2 and adds the consumed
exact-68 CDX bulk release. Its historical output-absence assertion is replaced
by immutable report/QA hash verification. No historical test is modified.

The current gate is:

```powershell
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v3
```

The runner fails construction if any of the seven historical methods or seven
explicit post-execution replacements is missing.
