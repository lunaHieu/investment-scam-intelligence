# Target Text Corpus V1 Wayback capture plan V1

The capture plan contains every candidate with a resolved Wayback snapshot and no unavailable candidate: 29 immutable targets split 5 regulator-linked, 7 CFTC RED-linked, 8 IAPD-linked, and 9 EDGAR-linked. This preserves the actual availability outcome; no missing quota is reallocated and no candidate is substituted in place.

Each row fixes the candidate identity, provenance channel, Wayback timestamp, discovered snapshot URL, `id_` raw-replay URL, and absolute local target path. Target paths are constrained beneath the project raw-data root and must not exist before execution. The plan and its upstream availability/QA artifacts are SHA-256 pinned.

Independent QA must pass and the plan hash must be registered before download. The authorized executor uses at least six seconds between requests, follows redirects only within `web.archive.org`, refuses target reuse, preserves exact response bytes and hashes, and stops subsequent requests on HTTP 429. Live candidate domains, labels, model operations, validation, and test access remain outside this gate.
