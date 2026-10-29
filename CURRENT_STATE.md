# Current Project State

This file is the stable entry point for the project's current operational state.
Historical reports and registries remain immutable and can therefore contain
superseded next-step descriptions.

- Project direction and progress plan: [`docs/project-direction-plan-r18.md`](docs/project-direction-plan-r18.md), incorporating unchanged R2-R17 content
- Reproducibility guide: [`docs/reproducibility-current-state-v52.md`](docs/reproducibility-current-state-v52.md)
- Current gap ledger: [`registry/analyses/project_state_gap_ledger_v55.json`](registry/analyses/project_state_gap_ledger_v55.json)
- Current repository quality gate: [`docs/current-test-suite-lifecycle-v7.md`](docs/current-test-suite-lifecycle-v7.md)
- Crimson primary-review readiness: [`registry/analyses/crimson_primary_review_readiness_v1.json`](registry/analyses/crimson_primary_review_readiness_v1.json)
- Immutable B5 continuation result: [`registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_continuation_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_continuation_result_v1.json)
- Immutable one-row CDX canary result: [`registry/analyses/target_text_corpus_v1_ready_channel_cdx_canary_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_cdx_canary_result_v1.json)
- Immutable exact-68 CDX bulk result: [`registry/analyses/target_text_corpus_v1_ready_channel_cdx_bulk_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_cdx_bulk_result_v1.json)
- Verified exact-53 capture plan: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_plan_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_plan_v1.json)
- Verified exact-53 capture release: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_release_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_release_v1.json)
- Immutable partial capture result: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_result_v1.json)
- Immutable exact-49 continuation result: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_result_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_result_v1.json)
- Immutable exact-48 continuation result V2: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_result_v2.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_result_v2.json)
- Verified exact-42 continuation plan V3: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_plan_v3.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_plan_v3.json)
- Verified exact-42 continuation release V3: [`registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_release_v3.json`](registry/analyses/target_text_corpus_v1_ready_channel_capture_continuation_release_v3.json)
- Raw-artifact security incident: [`registry/analyses/target_text_corpus_v1_ready_channel_raw_artifact_security_incident_v1.json`](registry/analyses/target_text_corpus_v1_ready_channel_raw_artifact_security_incident_v1.json)
- Raw-HTML branch abandonment: [`registry/analyses/target_text_corpus_v1_raw_html_branch_abandonment_v1.json`](registry/analyses/target_text_corpus_v1_raw_html_branch_abandonment_v1.json)
- Sanitized text-only inventory: [`registry/analyses/target_text_corpus_v1_sanitized_text_only_inventory_v1.json`](registry/analyses/target_text_corpus_v1_sanitized_text_only_inventory_v1.json)
- Sanitized text-only intake protocol: [`registry/analyses/target_text_corpus_v1_sanitized_text_only_intake_protocol_v1.json`](registry/analyses/target_text_corpus_v1_sanitized_text_only_intake_protocol_v1.json)
- Sanitized text-source assessment: [`registry/analyses/target_text_corpus_v1_sanitized_text_source_assessment_v1.json`](registry/analyses/target_text_corpus_v1_sanitized_text_source_assessment_v1.json)
- Sanitized text-source discovery specification: [`registry/analyses/target_text_corpus_v1_sanitized_text_source_discovery_spec_v1.json`](registry/analyses/target_text_corpus_v1_sanitized_text_source_discovery_spec_v1.json)
- Python dependency contract: [`docs/python-dependency-contract-v1.md`](docs/python-dependency-contract-v1.md)
- Repository quality audit: [`docs/repository-quality-audit-v1.md`](docs/repository-quality-audit-v1.md)

The B5 continuation, one-row canary and exact-68 CDX bulk release have executed
and must not be rerun. The exact-53 capture release stopped after 3 successes
and one below-minimum response; its exact-49 continuation then stopped on a
second below-minimum response, leaving 48 rows unattempted. Both failed rows are
quarantined. Exact-48 V2 then captured five rows and preserved one row-local
HTTP 404 before stopping, leaving 42 never-attempted rows. No capture release is
closed. After Defender quarantined a severe HTML Trojan, the owner permanently
abandoned the complete raw-HTML branch. No restoration, whitelist, transfer or
processing is authorized. The text-only inventory, intake protocol and offline
DFPI/UBCKNN/FCA assessment and new-source discovery specification are complete.
All three are evidence-only rather than fresh observed-text channels; next is a
separately frozen and verified bounded discovery release.
The referenced artifacts, hashes, cohort identities and
no-overwrite rules are authoritative. The current repository suite uses the
verified V7 bounded lifecycle-aware runner. The direction plan is a tracking guide, not a
release authorization. This pointer does not open any data, labeling,
validation, test, training, scoring or deployment gate.
