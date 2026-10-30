"""Run current tests after supplemental parser-bound V1 acquisition became immutable."""

import argparse
import unittest
from pathlib import Path

from scripts.run_current_test_suite_v1 import iter_tests
from scripts.run_current_test_suite_v8 import LIFECYCLE_REPLACEMENTS as V8


LIFECYCLE_REPLACEMENTS = {
    **V8,
    "test_target_text_corpus_v1_parser_bound_content_supplemental_release_v1.ParserBoundContentSupplementalReleaseV1Tests.test_exact_supplemental_population_is_verified_but_execution_closed": "test_current_artifact_lifecycle_v9.CurrentArtifactLifecycleV9Tests.test_supplemental_result_is_exact_and_independently_verified",
    "test_execute_target_text_corpus_v1_parser_bound_content_supplemental_v1.ParserBoundSupplementalExecutorV1Tests.test_pbc05_parser_failure_continues_three_never_attempted_rows": "test_current_artifact_lifecycle_v9.CurrentArtifactLifecycleV9Tests.test_pbc05_parser_failure_did_not_block_remaining_rows",
    "test_execute_target_text_corpus_v1_parser_bound_content_supplemental_v1.ParserBoundSupplementalExecutorV1Tests.test_transport_failure_stops_provider_requests": "test_current_artifact_lifecycle_v9.CurrentArtifactLifecycleV9Tests.test_supplemental_result_retains_no_raw_or_temporary_artifacts",
    "test_execute_target_text_corpus_v1_parser_bound_content_supplemental_v1.ParserBoundSupplementalExecutorV1Tests.test_existing_output_blocks_before_transport": "test_current_artifact_lifecycle_v9.CurrentArtifactLifecycleV9Tests.test_supplemental_rerun_is_blocked_before_transport",
    "test_target_text_corpus_v1_parser_bound_content_supplemental_live_gate_v1.ParserBoundSupplementalLiveGateV1Tests.test_protocol_and_exact_owner_amendment_verify": "test_current_artifact_lifecycle_v9.CurrentArtifactLifecycleV9Tests.test_supplemental_authorization_is_historical_and_downstream_gates_remain_closed",
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
