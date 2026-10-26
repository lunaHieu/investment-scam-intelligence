# Reproducibility current state V35

The active acquisition gate remains the exact-69 Wayback availability
continuation at `2026-10-26T23:20:12.335732+07:00`. Row `001` is quarantined
after three HTTP 429 responses and cannot be queried identically again.

A conditional fallback is now independently prepared but network-closed. It
cannot bypass the continuation. Only a final continuation report plus a
partial independent QA may activate a single CDX metadata canary for row
`002`. A valid canary permits preparation of a separate unresolved-only CDX
release; another 429 closes the archive-provider branch and routes the
population to non-archive source assessment.

The fallback has no automatic cascade, does not download archived pages, and
does not infer labels from availability or CDX membership. Capture,
validation/test access, scoring, and training remain closed.
