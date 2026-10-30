"""Run current tests after the exact PBC05/PBC08 diagnostic execution."""

import argparse
import unittest
from pathlib import Path

from scripts.run_current_test_suite_v9 import LIFECYCLE_REPLACEMENTS as V9
from scripts.run_current_test_suite_v1 import iter_tests


LIFECYCLE_REPLACEMENTS = {
    **V9,
    "test_target_text_corpus_v1_parser_bound_content_diagnostic_executor_v1.DiagnosticExecutorV1Tests.test_parser_failure_continues_exact_two_rows_with_pacing_and_no_raw_retention": "test_current_artifact_lifecycle_v10.CurrentArtifactLifecycleV10Tests.test_diagnostic_result_is_verified_with_exact_two_parser_rejections",
    "test_target_text_corpus_v1_parser_bound_content_diagnostic_executor_v1.DiagnosticExecutorV1Tests.test_existing_output_blocks_before_transport": "test_current_artifact_lifecycle_v10.CurrentArtifactLifecycleV10Tests.test_completed_diagnostic_result_closes_executor_preflight",
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
