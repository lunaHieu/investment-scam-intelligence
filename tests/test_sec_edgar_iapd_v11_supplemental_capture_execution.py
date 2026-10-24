import json
import unittest
from datetime import timedelta
from pathlib import Path

from scripts.build_sec_edgar_iapd_v11_supplemental_capture_release import parse_time
from scripts.execute_sec_edgar_iapd_v11_supplemental_capture import USER_AGENT, execute


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "configs" / "sec_edgar_iapd_v11_supplemental_capture_release_v1.json"
RELEASE_QA = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_supplemental_capture_plan_v1\independent_release_qa_v1.json")


class SecEdgarIapdV11SupplementalCaptureExecutionTests(unittest.TestCase):
    def test_pre_gate_fails_before_reserving_partial(self) -> None:
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        not_before = parse_time(release["execution_contract"]["not_before"])
        with self.assertRaises(PermissionError):
            execute(RELEASE, RELEASE_QA, now=not_before - timedelta(seconds=1))
        report = Path(release["planned_output"]["path"])
        self.assertFalse(report.exists())
        self.assertFalse(report.with_suffix(report.suffix + ".partial").exists())

    def test_user_agent_is_identifying_and_archive_only(self) -> None:
        self.assertIn("ISI-V11-Supplemental-Capture/1.0", USER_AGENT)
        self.assertIn("gpt-5", USER_AGENT)
        self.assertIn("https://github.com/lunaHieu/investment-scam-intelligence", USER_AGENT)


if __name__ == "__main__":
    unittest.main()
