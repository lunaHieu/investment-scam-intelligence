"""Run current tests after V3 execution and endpoint-security quarantine."""
import argparse,unittest
from pathlib import Path
from scripts.run_current_test_suite_v1 import iter_tests
from scripts.run_current_test_suite_v6 import LIFECYCLE_REPLACEMENTS as V6
LIFECYCLE_REPLACEMENTS={**V6,
'test_target_text_corpus_v1_ready_channel_capture_continuation_plan_v3.PlanV3Tests.test_exact_42_recomputes':'test_current_artifact_lifecycle_v7.CurrentArtifactLifecycleV7Tests.test_consumed_plan_and_report_are_pinned',
'test_target_text_corpus_v1_ready_channel_capture_continuation_release_v3.ReleaseV3Tests.test_release':'test_current_artifact_lifecycle_v7.CurrentArtifactLifecycleV7Tests.test_endpoint_security_incident_is_fail_closed'}
def build_current_suite(d,pattern='test_*.py'):
 t=list(iter_tests(unittest.defaultTestLoader.discover(str(d),pattern=pattern)));ids={x.id() for x in t};mh=set(LIFECYCLE_REPLACEMENTS)-ids;mr=set(LIFECYCLE_REPLACEMENTS.values())-ids
 if mh or mr:raise RuntimeError((mh,mr))
 return unittest.TestSuite(x for x in t if x.id() not in LIFECYCLE_REPLACEMENTS)
def main():
 p=argparse.ArgumentParser();p.add_argument('--start-dir',type=Path,default=Path('tests'));p.add_argument('--verbosity',type=int,default=1);a=p.parse_args();s=build_current_suite(a.start_dir);print(f'historical_preexecution_methods_superseded={len(LIFECYCLE_REPLACEMENTS)}');r=unittest.TextTestRunner(verbosity=a.verbosity).run(s);return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
