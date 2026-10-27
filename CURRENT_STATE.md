# Current Project State

This file is the stable entry point for the project's current operational state.
Historical reports and registries remain immutable and can therefore contain
superseded next-step descriptions.

- Project direction and progress plan: [`docs/project-direction-plan-r4.md`](docs/project-direction-plan-r4.md), incorporating unchanged R2-R3 content
- Reproducibility guide: [`docs/reproducibility-current-state-v38.md`](docs/reproducibility-current-state-v38.md)
- Current gap ledger: [`registry/analyses/project_state_gap_ledger_v41.json`](registry/analyses/project_state_gap_ledger_v41.json)
- Current repository quality gate: [`docs/current-test-suite-lifecycle-v1.md`](docs/current-test-suite-lifecycle-v1.md)
- Crimson primary-review readiness: [`registry/analyses/crimson_primary_review_readiness_v1.json`](registry/analyses/crimson_primary_review_readiness_v1.json)
- Immutable B5 continuation result: [`registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_continuation_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_continuation_result_v1.json)
- Active one-row CDX metadata canary: [`configs/target_text_corpus_v1_ready_channel_cdx_canary_release_v1.json`](configs/target_text_corpus_v1_ready_channel_cdx_canary_release_v1.json)
- Python dependency contract: [`docs/python-dependency-contract-v1.md`](docs/python-dependency-contract-v1.md)
- Repository quality audit: [`docs/repository-quality-audit-v1.md`](docs/repository-quality-audit-v1.md)

The B5 continuation has executed and must not be rerun. The active canary is
network-closed until `2026-10-28T09:32:33.798697+07:00`. The referenced
artifacts, hashes, cohort identities, time gates and no-overwrite rules are
authoritative. The current repository suite passes 1006/1006 tests using the
bounded lifecycle-aware runner. The direction plan is a tracking guide, not a
release authorization. This pointer does not open any data, labeling,
validation, test, training, scoring or deployment gate.
