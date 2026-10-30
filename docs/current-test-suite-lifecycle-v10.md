# Current Test Suite Lifecycle V10

V10 supersedes two diagnostic-executor tests that required the result output to
be absent. The exact two-row PBC05/PBC08 result now exists, so replacements
verify the immutable result and that completed output closes executor
preflight. Historical test files remain unchanged.

Run the current suite with:

`.venv\Scripts\python.exe -m scripts.run_current_test_suite_v10`
