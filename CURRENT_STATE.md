# Current Project State

This file is the stable entry point for the project's current operational state.
Historical reports and registries remain immutable and can therefore contain
superseded next-step descriptions.

- Project direction and progress plan: [`docs/project-direction-plan-r7.md`](docs/project-direction-plan-r7.md), incorporating unchanged R2-R6 content
- Reproducibility guide: [`docs/reproducibility-current-state-v41.md`](docs/reproducibility-current-state-v41.md)
- Current gap ledger: [`registry/analyses/project_state_gap_ledger_v44.json`](registry/analyses/project_state_gap_ledger_v44.json)
- Current repository quality gate: [`docs/current-test-suite-lifecycle-v3.md`](docs/current-test-suite-lifecycle-v3.md)
- Crimson primary-review readiness: [`registry/analyses/crimson_primary_review_readiness_v1.json`](registry/analyses/crimson_primary_review_readiness_v1.json)
- Immutable B5 continuation result: [`registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_continuation_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_continuation_result_v1.json)
- Immutable one-row CDX canary result: [`registry/analyses/target_text_corpus_v1_ready_channel_cdx_canary_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_cdx_canary_result_v1.json)
- Immutable exact-68 CDX bulk result: [`registry/analyses/target_text_corpus_v1_ready_channel_cdx_bulk_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_cdx_bulk_result_v1.json)
- Verified exact-53 capture plan: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_plan_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_plan_v1.json)
- Verified exact-53 capture release: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_release_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_release_v1.json)
- Python dependency contract: [`docs/python-dependency-contract-v1.md`](docs/python-dependency-contract-v1.md)
- Repository quality audit: [`docs/repository-quality-audit-v1.md`](docs/repository-quality-audit-v1.md)

The B5 continuation, one-row canary and exact-68 CDX bulk release have executed
and must not be rerun. The exact-53 capture release is verified and immediately
eligible, but has not run. The referenced artifacts, hashes, cohort identities and
no-overwrite rules are authoritative. The current repository suite uses the
verified V3 bounded lifecycle-aware runner. The direction plan is a tracking guide, not a
release authorization. This pointer does not open any data, labeling,
validation, test, training, scoring or deployment gate.
