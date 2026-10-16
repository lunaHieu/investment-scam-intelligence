# SEC EDGAR/IAPD Wayback capture execution tooling V2

## Step name

Bind capture execution to the final availability evidence and a 24-hour cooldown.

## Meaning

V1 froze the correct archive-only execution contract but required only that
`not_before` not precede release creation. V2 additionally binds the concrete
release to the generation, path, SHA-256, report ID and `created_at` of the final
availability result already pinned by capture-plan V2. Both builder and
independent verifier recompute the earliest permitted execution time as final
availability `created_at + 86,400 seconds`; even one second less fails closed.

All V1 network and immutability controls remain unchanged: only
`https://web.archive.org` raw replay URLs, at least 30 seconds per request, one
attempt per snapshot, at most three archive-internal redirects, HTML no larger
than 25 MiB, immediate stop on HTTP 429, preserved failures, no replacement and
no report or partial-report overwrite. The independent verifier reloads and
hash-checks plan, plan QA and final availability evidence, reconstructs the
cooldown, verifies every raw replay URL, and confirms the output target remains
absent.

The release schema identity and PASS status remain compatible with the frozen
V1 archive executor and raw-byte result verifier. A synthetic offline test calls
the executor's preflight validation only; it performs no network request.

## Current gate

This is predeclared offline tooling. It creates no concrete execution release,
capture report or raw HTML and makes no network request. A real release may be
created only after capture-plan V2 and its independent QA pass, with
`not_before` at least 24 hours after the final availability report. Candidate
live domains, text extraction, labels, validation/test, model operations and
training remain closed.
