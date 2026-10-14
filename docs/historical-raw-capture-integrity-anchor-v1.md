# Historical raw capture integrity anchor V1

## Step and meaning

This is project-state step P2D. It places a Git-rooted integrity anchor on 11 pre-existing capture report/run files whose recorded SHA-256 values match all 87 raw files left uncovered by P2B. It excludes downstream `usable_capture_view` files, so the anchor is based on acquisition records rather than later selection views.

The anchor is explicitly retrospective. It preserves the current reports and bytes; it does not invent an acquisition log, rewrite a date, create a label, or promote a file into any model partition.

## Frozen result

- Evidence documents anchored: 11.
- Previously uncovered raw files represented with matching hashes: 87/87.
- Conflicting raw hash claims: 0.
- Historical capture records modified: 0.
- Files promoted: 0.

The independent verifier recomputes the exact evidence-document set from the P2C triage, verifies every evidence-document hash, and requires every one of the 87 rows to have matching evidence from the anchor. The next gate is a fresh full-corpus provenance recomputation; complete coverage must not be claimed from this anchor alone.
