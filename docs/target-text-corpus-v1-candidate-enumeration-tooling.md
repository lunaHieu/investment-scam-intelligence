# Target Text Corpus V1 candidate-enumeration tooling

Status: **offline implementation verified; production enumeration not run**.

The implementation turns four already normalized and independently authorized reference inputs into one complete balanced provenance queue. It performs no network request, opens no domain, captures no artifact, assigns no binary label, and runs no model.

## Fail-closed behavior

The command refuses to run unless a later versioned prerequisite ledger states that both external inputs are `READY` and releases offline enumeration only. It independently checks that:

- the CFTC artifact exists and its bytes match the registered SHA-256;
- the private SEC identity file exists outside the public repository;
- the private file contains the exact three required fields, a syntactically valid contact email, and a project-matching research purpose;
- the private file hash and contents are absent from the public ledger; and
- the ledger keeps network execution disabled.

No output is written if any channel falls below quota. The missing quota is not reallocated. Existing output paths are never overwritten.

## Selection and exclusion

Each normalized input row must carry exact reference provenance, an entity name, candidate URL and normalized host, identity-linkage rationale, and passing opened-cohort/legacy exclusion states. The implementation rejects unregistered channel/source combinations, invalid reference hashes, host mismatches, duplicate reference records, same-channel duplicate hosts, cross-channel host overlap, and entity overlap across the planned target strata.

Eligible rows are ranked by the predeclared SHA-256 key and selected at the frozen per-channel quota. Every emitted row is then checked against the frozen candidate invariants. It remains `UNCERTAIN`, `LOW`, `UNREVIEWED`, `training_eligible: NO`, and records that neither Wayback nor a live domain has been queried.

## Verification performed now

Synthetic fixtures exercise deterministic balance, channel shortfall, cross-channel host collisions, cross-stratum entity collisions, exclusion failures, and refusal of the current missing-input ledger. Synthetic fixtures are tests only and are not candidate records or research data.

The production command must not be executed until a new independently verified readiness ledger exists. The current ledger correctly blocks it.
