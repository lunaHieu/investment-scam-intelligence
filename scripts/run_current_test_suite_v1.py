"""Run the current repository suite without replaying consumed pre-execution assertions.

The excluded methods are immutable historical tests whose only failing assertion
is that a one-shot output does not exist.  Every exclusion is paired with an
explicit post-execution replacement test.  This runner refuses to continue if
either side of that mapping disappears, so the list cannot silently expand.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from typing import Iterable


LIFECYCLE_REPLACEMENTS = {
    "test_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1."
    "AlternateSnapshotCdxOwnerOverrideV1Tests.test_real_override_changes_only_timing_and_verifies":
        "test_current_artifact_lifecycle_v1.CurrentArtifactLifecycleV1Tests."
        "test_owner_override_verifies_after_consumption",
    "test_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1."
    "AlternateSnapshotCdxOwnerOverrideV1Tests.test_early_execution_and_result_are_hash_bound_without_page_download":
        "test_current_artifact_lifecycle_v1.CurrentArtifactLifecycleV1Tests."
        "test_owner_override_synthetic_execution_uses_explicit_output",
    "test_sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1."
    "AlternateSnapshotCdxReleaseV1Tests.test_real_release_passes_independent_offline_verification":
        "test_current_artifact_lifecycle_v1.CurrentArtifactLifecycleV1Tests."
        "test_alternate_cdx_release_verifies_after_consumption",
    "test_target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2."
    "ReadyChannelAvailabilityExecutionAmendmentV2Tests.test_real_amendment_recomputes_canonical_empty_and_exact_70":
        "test_current_artifact_lifecycle_v1.CurrentArtifactLifecycleV1Tests."
        "test_b5_amendment_verifies_after_consumption",
    "test_target_text_corpus_v1_ready_channel_wayback_availability_execution_v1."
    "ReadyChannelWaybackAvailabilityExecutionV1Tests.test_real_release_is_exact_70_and_network_closed_at_freeze":
        "test_current_artifact_lifecycle_v1.CurrentArtifactLifecycleV1Tests."
        "test_b4_release_verifies_after_consumption",
}


def iter_tests(suite: unittest.TestSuite) -> Iterable[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def build_current_suite(start_dir: Path, pattern: str = "test_*.py") -> unittest.TestSuite:
    discovered = unittest.defaultTestLoader.discover(str(start_dir), pattern=pattern)
    tests = list(iter_tests(discovered))
    by_id = {test.id(): test for test in tests}
    historical = set(LIFECYCLE_REPLACEMENTS)
    replacements = set(LIFECYCLE_REPLACEMENTS.values())
    missing_historical = sorted(historical - set(by_id))
    missing_replacements = sorted(replacements - set(by_id))
    if missing_historical or missing_replacements:
        details = []
        if missing_historical:
            details.append(f"missing historical tests: {missing_historical}")
        if missing_replacements:
            details.append(f"missing replacement tests: {missing_replacements}")
        raise RuntimeError("; ".join(details))
    return unittest.TestSuite(test for test in tests if test.id() not in historical)


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
