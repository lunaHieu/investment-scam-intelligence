# Unanchored raw provenance triage V1

## Step and meaning

This is project-state step P2C. It investigates the 87 files left uncovered by the strict P2B Git-rooted provenance audit. It searches only pre-existing local acquisition, capture, manifest, and artifact-audit JSON documents and compares every recorded SHA-256 value with the current raw bytes.

This step discovers evidence; it does not convert that evidence into a trusted Git anchor and does not promote any raw file.

## Frozen result

- P2B uncovered population: 87 files.
- Pre-existing evidence documents scanned: 42.
- Files with at least one matching unanchored hash record: 87.
- Files with conflicting local hash evidence: 0.
- Files with no local hash evidence: 0.
- Evidence JSON parse failures: 0.
- Files promoted: 0.

The result narrows the problem from missing provenance evidence to missing provenance anchoring. The existing capture reports and audits predate this triage and their own hashes are recorded in the output, so a later registration can be explicit and reproducible without inventing or backdating an acquisition event.

## Decision

Status is `PASS_GAPS_CLASSIFIED_NO_PROMOTION`. The next gate is an independent retrospective integrity anchor containing the exact pre-existing evidence-document set and hashes. That gate must preserve the original capture outcomes, keep all label and model gates closed, and rerun full raw coverage from scratch afterward.

The authoritative output is:

`D:\nckh 2026-2027\ISI_Data\derived\project_state_audit_v1\unanchored_raw_provenance_triage_v1.json`

SHA-256: `6a22236beddb5abc8948380600e546432584b5083ab574006203f6448e40a7cb`.
