# Target-text corpus V1 ready-channel queue V1

## Purpose

B2 materializes the exact offline provenance queue authorized by B1 for the two channels whose post-exclusion capacity is already sufficient. It creates candidates, not evidence and not labels.

## Frozen population

- `CONFIRMED_REGULATOR_LINKED_WEBSITE`: 25 `DEVELOPMENT` and 10 `EXTERNAL_HOLDOUT` candidates.
- `LEGITIMATE_REGISTER_LINKED_WEBSITE`: 25 `DEVELOPMENT` and 10 `EXTERNAL_HOLDOUT` candidates.
- Total: 70 candidates, comprising 50 development and 20 external-holdout rows.

Selection is deterministic from the B1 seed and cohort namespaces. Development is selected first. The holdout then excludes every selected development host and normalized entity. Across the entire queue, candidate IDs, normalized hosts, and normalized entities must each be unique.

## Exclusions and safety

The builder repeats B1's frozen screens against previously opened/enumerated hosts, the prior SEC/IAPD population, cross-channel host collisions, and cross-stratum normalized-entity collisions. Every row remains `UNCERTAIN`, unreviewed, unlabeled, ineligible for training, and ineligible for model scoring.

B2 performs no network request, live-domain access, Wayback query, artifact capture, validation/test opening, scoring, or training. Its independent verifier reconstructs membership and order from the frozen reference pools rather than trusting queue aggregates.

## Commands

From the repository root, using the project environment:

```powershell
.venv\Scripts\python.exe -m scripts.build_target_text_corpus_v1_ready_channel_queue_v1 --config configs\target_text_corpus_v1_ready_channel_queue_release_v1.json --verify-only
.venv\Scripts\python.exe -m scripts.build_target_text_corpus_v1_ready_channel_queue_v1 --config configs\target_text_corpus_v1_ready_channel_queue_release_v1.json
.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_ready_channel_queue_v1 --config configs\target_text_corpus_v1_ready_channel_queue_release_v1.json --output "D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_enumeration_release_v1\independent_queue_qa_v1.json"
```

The two output artifacts and independent QA are immutable. Existing final or `.partial` files are never overwritten.

## Next gate

Only a passing independent B2 QA permits preparation of B3: a separately frozen and independently verified Wayback availability-query release for these exact 70 identities. B2 itself does not authorize network execution or capture.
