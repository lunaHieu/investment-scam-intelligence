# Current Test Suite Lifecycle V4

V4 preserves seven prior lifecycle transitions and replaces four consumed
capture-stage pre-execution assertions with immutable plan, tooling,
partial-result and independent-QA hash checks. No historical test is modified.

Current gate:

```powershell
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v4
```
