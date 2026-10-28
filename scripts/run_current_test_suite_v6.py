"""Run current tests after the exact-48 continuation release was consumed."""
from __future__ import annotations
import argparse, unittest
from pathlib import Path
from scripts.run_current_test_suite_v1 import iter_tests
from scripts.run_current_test_suite_v5 import LIFECYCLE_REPLACEMENTS as V5_REPLACEMENTS

LIFECYCLE_REPLACEMENTS={**V5_REPLACEMENTS,
 "test_target_text_corpus_v1_ready_channel_capture_continuation_release_v2.ContinuationReleaseV2Tests.test_real_release_is_exact_48_and_verified":
 "test_current_artifact_lifecycle_v6.CurrentArtifactLifecycleV6Tests.test_consumed_exact_48_continuation_and_partial_result_verify",
 "test_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1.ReadyChannelCaptureContinuationPlanV1Tests.test_exact_49_excludes_successes_and_failure":
 "test_current_artifact_lifecycle_v6.CurrentArtifactLifecycleV6Tests.test_consumed_exact_49_plan_membership",
 "test_target_text_corpus_v1_ready_channel_capture_continuation_plan_v1.ReadyChannelCaptureContinuationPlanV1Tests.test_independent_full_recomputation_passes":
 "test_current_artifact_lifecycle_v6.CurrentArtifactLifecycleV6Tests.test_consumed_exact_49_plan_qa",
 "test_target_text_corpus_v1_ready_channel_capture_continuation_plan_v2.ContinuationPlanV2Tests.test_real_plan_is_exact_48_and_recomputes":
 "test_current_artifact_lifecycle_v6.CurrentArtifactLifecycleV6Tests.test_consumed_exact_48_plan_membership",
 "test_target_text_corpus_v1_ready_channel_capture_continuation_plan_v2.ContinuationPlanV2Tests.test_failed_rows_are_disjoint":
 "test_current_artifact_lifecycle_v6.CurrentArtifactLifecycleV6Tests.test_consumed_exact_48_plan_qa"}

def build_current_suite(start_dir:Path,pattern:str="test_*.py"):
 tests=list(iter_tests(unittest.defaultTestLoader.discover(str(start_dir),pattern=pattern)));by_id={t.id():t for t in tests}
 missing_h=sorted(set(LIFECYCLE_REPLACEMENTS)-set(by_id));missing_r=sorted(set(LIFECYCLE_REPLACEMENTS.values())-set(by_id))
 if missing_h or missing_r: raise RuntimeError(f"missing historical={missing_h}; missing replacements={missing_r}")
 return unittest.TestSuite(t for t in tests if t.id() not in LIFECYCLE_REPLACEMENTS)

def main():
 p=argparse.ArgumentParser();p.add_argument('--start-dir',type=Path,default=Path('tests'));p.add_argument('--pattern',default='test_*.py');p.add_argument('--verbosity',type=int,choices=(0,1,2),default=1);a=p.parse_args()
 suite=build_current_suite(a.start_dir,a.pattern);print(f"historical_preexecution_methods_superseded={len(LIFECYCLE_REPLACEMENTS)}");r=unittest.TextTestRunner(verbosity=a.verbosity).run(suite);return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
