# Current Test Suite Lifecycle V1

Date: 2026-10-27  
Status: active current-suite contract

Five assertions in four hash-pinned historical test modules were written for
the pre-execution state. They require that one-shot output paths do not exist.
Those releases have since executed, their outputs are immutable, and their
independent result QA is registered. Re-running the assertions now produces
four failures and one error even though the artifacts remain valid.

The historical files, releases, verifiers and outputs are unchanged. The
current suite runner excludes exactly the five obsolete pre-execution methods
and refuses to run if any excluded method or its explicit post-execution
replacement is missing. The replacements verify the original releases with
their supported `require_output_absent=False` mode, pin the consumed output and
QA hashes, and retain the synthetic no-page-download behavior check.

Run the current suite with:

```powershell
.venv\Scripts\python.exe -m scripts.run_current_test_suite_v1
```

Direct `unittest discover` remains useful as a historical diagnostic and is
expected to report the five superseded pre-execution transitions on the
canonical machine. It is not the current post-execution quality gate.

This change performs no network operation, changes no label, opens no dataset
split and authorizes no model operation.
