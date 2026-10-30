# Current Test Suite Lifecycle V8

V8 supersedes eight parser-bound pre-execution assertions after the immutable V1
result was created. Their replacements verify the real result, closed
downstream gates, absence of raw and temporary artifacts, the historical audit
snapshot and fail-closed prevention of any V1 rerun before an HTTP opener.

Historical tests remain unchanged. The current quality gate is:

`.venv\Scripts\python.exe -m scripts.run_current_test_suite_v8`
