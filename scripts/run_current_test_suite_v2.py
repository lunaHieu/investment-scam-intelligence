"""Run the current suite after the ready-channel CDX canary was consumed."""

from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from scripts.run_current_test_suite_v1 import LIFECYCLE_REPLACEMENTS as V1_REPLACEMENTS, iter_tests


LIFECYCLE_REPLACEMENTS = {
    **V1_REPLACEMENTS,
    "test_target_text_corpus_v1_ready_channel_cdx_canary_v1."
    "ReadyChannelCdxCanaryV1Tests.test_real_release_passes_independent_verification":
        "test_current_artifact_lifecycle_v2.CurrentArtifactLifecycleV2Tests."
        "test_consumed_canary_release_and_result_verify",
}


def build_current_suite(start_dir: Path, pattern: str = "test_*.py") -> unittest.TestSuite:
    tests = list(iter_tests(unittest.defaultTestLoader.discover(str(start_dir), pattern=pattern)))
    by_id = {test.id(): test for test in tests}
    missing_historical = sorted(set(LIFECYCLE_REPLACEMENTS) - set(by_id))
    missing_replacements = sorted(set(LIFECYCLE_REPLACEMENTS.values()) - set(by_id))
    if missing_historical or missing_replacements:
        raise RuntimeError(f"missing historical={missing_historical}; missing replacements={missing_replacements}")
    return unittest.TestSuite(test for test in tests if test.id() not in LIFECYCLE_REPLACEMENTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-dir", type=Path, default=Path("tests"))
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--verbosity", type=int, choices=(0, 1, 2), default=1)
    args = parser.parse_args()
    suite = build_current_suite(args.start_dir, args.pattern)
    print(f"historical_preexecution_methods_superseded={len(LIFECYCLE_REPLACEMENTS)}")
    result = unittest.TextTestRunner(verbosity=args.verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
