"""Run current tests after parser-bound V1 acquisition became immutable."""

import argparse
import unittest
from pathlib import Path

from scripts.run_current_test_suite_v1 import iter_tests
from scripts.run_current_test_suite_v7 import LIFECYCLE_REPLACEMENTS as V7


LIFECYCLE_REPLACEMENTS = {
    **V7,
    "test_execute_target_text_corpus_v1_parser_bound_content_v1.ParserBoundExecutorV1Tests.test_preflight_keeps_execution_closed_before_and_after_commit": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_parser_bound_result_is_pinned_and_independently_verified",
    "test_audit_target_text_corpus_v1_parser_bound_execution_readiness_v1.ParserBoundExecutionReadinessAuditV1Tests.test_local_stack_is_ready_only_for_commit_review": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_parser_bound_result_keeps_downstream_gates_closed",
    "test_audit_target_text_corpus_v1_parser_bound_execution_readiness_v1.ParserBoundExecutionReadinessAuditV1Tests.test_network_surface_is_exactly_one_capability_gated_module": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_parser_bound_result_retains_no_raw_or_temporary_artifacts",
    "test_audit_target_text_corpus_v1_parser_bound_execution_readiness_v1.ParserBoundExecutionReadinessAuditV1Tests.test_pdf_runtime_and_git_lineage_are_pinned": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_historical_readiness_audit_snapshot_remains_closed",
    "test_orchestrate_target_text_corpus_v1_parser_bound_content_v1.ParserBoundProductionOrchestratorV1Tests.test_live_execution_is_blocked_before_real_opener": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_original_v1_rerun_is_blocked_before_real_opener",
    "test_http_transport_target_text_corpus_v1_parser_bound_content_v1.ParserBoundHttpTransportV1Tests.test_live_capability_is_closed_while_candidate_is_uncommitted": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_original_v1_http_capability_is_unavailable_after_result",
    "test_target_text_corpus_v1_parser_bound_content_execution_amendment_v1.ParserBoundExecutionAmendmentV1Tests.test_owner_authorized_scope_verifies_without_expanding_git_permission": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_original_owner_amendment_is_historical_and_result_is_pinned",
    "test_target_text_corpus_v1_parser_bound_content_execution_authorization_protocol_v1.ParserBoundExecutionAuthorizationProtocolV1Tests.test_committed_stack_is_bound_but_execution_remains_closed": "test_current_artifact_lifecycle_v8.CurrentArtifactLifecycleV8Tests.test_original_authorization_protocol_is_historical_and_closed",
}


def build_current_suite(directory: Path, pattern: str = "test_*.py") -> unittest.TestSuite:
    tests = list(iter_tests(unittest.defaultTestLoader.discover(str(directory), pattern=pattern)))
    ids = {test.id() for test in tests}
    missing_historical = set(LIFECYCLE_REPLACEMENTS) - ids
    missing_replacements = set(LIFECYCLE_REPLACEMENTS.values()) - ids
    if missing_historical or missing_replacements:
        raise RuntimeError((missing_historical, missing_replacements))
    return unittest.TestSuite(test for test in tests if test.id() not in LIFECYCLE_REPLACEMENTS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-dir", type=Path, default=Path("tests"))
    parser.add_argument("--verbosity", type=int, default=1)
    args = parser.parse_args()
    suite = build_current_suite(args.start_dir)
    print(f"historical_preexecution_methods_superseded={len(LIFECYCLE_REPLACEMENTS)}")
    result = unittest.TextTestRunner(verbosity=args.verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
