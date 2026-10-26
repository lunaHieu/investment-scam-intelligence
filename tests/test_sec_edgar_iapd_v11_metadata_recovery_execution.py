import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts.execute_sec_edgar_iapd_v11_metadata_recovery import USER_AGENT, execute


class V11MetadataRecoveryExecutionTests(unittest.TestCase):
    def test_user_agent_is_identifying(self) -> None:
        self.assertIn("gpt-5", USER_AGENT)
        self.assertIn("https://github.com/lunaHieu/investment-scam-intelligence", USER_AGENT)

    def test_closed_gate_is_checked_before_output_validation(self) -> None:
        release = Path("configs/sec_edgar_iapd_v11_metadata_recovery_release_v1.json")
        qa = Path(r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\sec_edgar_iapd_v11_metadata_recovery_plan_v1\independent_release_qa_v3.json")
        data = json.loads(release.read_text(encoding="utf-8"))
        gate = datetime.fromisoformat(data["execution_contract"]["not_before"])
        with self.assertRaises(PermissionError):
            execute(release, qa, now=gate - timedelta(seconds=1))


if __name__ == "__main__":
    unittest.main()
