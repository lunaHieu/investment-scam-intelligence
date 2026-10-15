# Reproducibility guide — current project state V1

Snapshot date: 2026-10-15 (Asia/Saigon).

## Purpose

This guide is the shortest auditable path from repository checkout to the current research state. It distinguishes immutable evidence, review recommendations, accepted diagnostic labels, model references, and gates that are still closed.

## Storage and trust boundaries

- Git repository: `C:\Users\hieu\Documents\ChatGPT\invesment scam intelligence`
- External data root: `D:\nckh 2026-2027\ISI_Data`
- Python runtime: `.venv\Scripts\python.exe`
- Raw data is intentionally outside Git. Git stores manifests, protocols, hashes, decisions, and verifiers.
- A local file is not trusted merely because it exists. Current raw trust requires a transitive SHA-256 chain rooted in committed JSON.
- Candidate live domains must not be accessed. Approved acquisition branches use official files or archive endpoints under frozen releases.

## Data and evidence flow

```text
source terms / protocol
        ↓
immutable raw artifact + SHA-256
        ↓
offline normalization / exact-text extraction
        ↓
case, entity, domain-family, clone, near-duplicate grouping
        ↓
primary evidence review
        ↓
blind second review
        ↓
explicit reconciliation and owner acceptance
        ↓
group-disjoint development / external-holdout release
        ↓
predeclared model development gates
```

Skipping a layer does not inherit the permissions of a later layer. In particular, registry membership, archive availability, or captured content does not create a binary label.

## Current checkpoints

### Raw corpus

The authoritative audit is `registry/analyses/raw_cross_registry_provenance_audit_v2.json`. It covers 278/278 existing files and 1,640,058,635 bytes with no existing-file hash mismatch. Two historical capture targets remain absent and excluded: `luctra.net` (possible security quarantine) and `finrafx.com` (security/IO block).

### External 21-record intake

`registry/pilots/external_text_reconciled_pilot_v1.json` records 10 `CONFIRMED` and 11 `LEGITIMATE` owner-adopted AI-assisted decisions. They are diagnostic/reporting eligible, not independently human evidence-rereviewed gold.

### Crimson

AI first-pass evidence covers all 40 planned records. Only one human first review is recorded; 39 first reviews, 21 second reviews, and 16 live-source gaps remain. No Crimson record is training eligible.

### Target Text Corpus pilot

Twenty-two captured artifacts completed grouping, primary review, blind second review, reconciliation, and owner acceptance. The result is 4 `CONFIRMED`, 11 `LEGITIMATE`, and 7 `UNCERTAIN`. The 15 decisive records remain diagnostic; training eligibility is zero and the V1-Core development gate is not met.

### Model state

The internal reference remains word unigram+bigram TF-IDF with regularized logistic regression. Character, stop-word/style-guard, and frozen E5 challengers failed their predeclared gates. No current model is approved for deployment. `registry/analyses/text_model_choice_dossier_v5.json` defines the next permissible model decision.

### Timed and manual gates

- SEC/IAPD V4 availability retry: execute exactly once no earlier than `2026-10-16T00:48:55.969405+07:00`.
- Vietnamese supply: zero verified rows; at least eight `CONFIRMED` and eight `LEGITIMATE` groups are required.
- Image branch: zero usable assets.
- DFPI/Vietnamese/manual source artifacts remain user-supplied or permission-dependent.

## Verification commands

Run commands from the repository root. Repository scripts are invoked as modules.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe -m scripts.verify_historical_raw_capture_integrity_anchor_v1
.venv\Scripts\python.exe -m unittest tests.test_raw_cross_registry_provenance_audit_registry_v2
.venv\Scripts\python.exe -m unittest tests.test_project_state_gap_ledger_v2
.venv\Scripts\python.exe -m unittest tests.test_text_model_choice_dossier_v5
```

The complete raw audit refuses overwrite. A fresh rerun must use a new, explicitly named output and be registered separately; do not replace the frozen V2 output.

## Reproducible claims and prohibited claims

Supported:

- every currently stored raw file has a Git-rooted hash chain;
- the current sparse text model is an internal reference, not a deployment model;
- the E5 challenger failed all six development gates under its exact frozen protocol;
- data/source robustness is the current bottleneck;
- manual and timed acquisition gaps remain.

Not supported:

- that every source label is verified investment-scam ground truth;
- that SEC/IAPD identity implies legitimacy;
- that regulator warning membership alone proves the captured solicitation is fraudulent;
- that the 21-record intake or 15-record target-text diagnostic set is double-reviewed human gold;
- that a larger transformer or AI agent will improve the classifier;
- that missing or endpoint-quarantined artifacts may be recreated or bypassed.

## Authoritative navigation

Start with:

1. `registry/analyses/project_state_gap_ledger_v2.json`
2. `registry/analyses/raw_cross_registry_provenance_audit_v2.json`
3. `registry/analyses/text_model_choice_dossier_v5.json`
4. `registry/analyses/sec_edgar_iapd_wayback_availability_retry_release_v4.json`

Then follow the hash-pinned inputs named by the relevant registry. Conversation history is explanatory context, not an authoritative artifact.
