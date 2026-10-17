# SEC EDGAR/IAPD Wayback capture execution tooling V3

## Step name

Predeclare the V6-aware, cooldown-bound archive capture release.

## Meaning

The V3 release builder accepts only a capture plan produced by capture-plan
tooling V3 and its exact independent QA V3. It binds the release to plan and QA
hashes and to the final availability generation, path, hash, report identity
and `created_at`. The independent verifier reloads each input and reconstructs
those bindings rather than trusting the release summary.

The earliest execution time is recomputed as final availability `created_at +
86,400 seconds`. The exact boundary passes; one second earlier fails. Release
creation time must not be later than `not_before`.

Network and immutability rules remain frozen: only raw Wayback replay at
`https://web.archive.org`, at least 30 seconds between requests, one attempt per
snapshot, immediate stop on HTTP 429, no live candidate-domain access, no
replacement of failed rows and no overwrite of an existing report or partial
report. The report identity and release schema identity remain compatible with
the frozen V1 executor and byte-hash result verifier; `tooling_version=v3` and
the V3 independent release-QA identity record the stronger preparation path.

## Current gate

This is offline preparation only. No concrete release, report or raw HTML is
created and no network request is made. Execution may occur only after a real
V3 plan and QA exist and the final-availability cooldown has elapsed. Text
extraction, labels, validation/test and training remain closed.
