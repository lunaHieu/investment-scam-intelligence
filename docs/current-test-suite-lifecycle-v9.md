# Current Test Suite Lifecycle V9

V9 supersedes five supplemental parser-bound pre-execution assertions after
the immutable four-row supplemental result was created. Their replacements
verify the real result, the row-local nature of the two parser rejections,
successful continuation through PBC06 and PBC07, absence of retained raw or
temporary artifacts, fail-closed rerun prevention, and closed downstream
gates.

The historical tests remain unchanged. They are excluded only from the
current-state quality gate because their required precondition—absence of the
supplemental output—is no longer true. The current quality gate is:

`.venv\Scripts\python.exe -m scripts.run_current_test_suite_v9`
