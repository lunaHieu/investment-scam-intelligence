# SEC EDGAR/IAPD Capture Execution Tooling V5

Date: 2026-10-20
Status: frozen offline; concrete capture not yet executed

V5 binds a concrete archive-only capture release to the independently verified
partial-resolved V8 capture plan. It preserves the exact 58-row membership,
order, cohort identity, raw replay URLs, output paths, and plan/QA hashes.

The release cannot execute before 24 hours after the V8 availability report.
Execution uses only `web.archive.org`, raw replay, at least 30 seconds pacing,
one attempt per snapshot, immediate HTTP 429 stop, immutable output paths, and
independent raw-byte/hash verification. Partial capture cannot open extraction.

Candidate live domains, labeling, validation/test access, model scoring, and
training remain prohibited.
