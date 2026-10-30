# PBC Diagnostic Execution Tooling V1

An exact two-row executor and independent result verifier are prepared for
PBC05 and PBC08. The executor reserves a no-resume partial journal before
transport, follows no redirects, enforces a 30-second interval, stops after a
transport/provider error, applies the fixed parser diagnostic codes, and
refuses existing result or partial paths.

The owner authorization is recorded for this release hash only, with at most
two requests and one attempt per resource. It does not authorize retries or
dataset/model work.

Offline checks passed: eight focused tests, current suite V9 at 1158 tests,
registry validation, and `git diff --check`. The executor preflight correctly
remains closed because this tooling is local and uncommitted. No source request
has been made. Execution requires this tooling and its QA to be committed on
`main`, a clean tree equal to `origin/main`, and the existing authorization to
remain bound to the exact release hash.
