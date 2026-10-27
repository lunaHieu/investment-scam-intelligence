import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1 import execute
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_result_v1 import verify as verify_override_result
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1 import (
    PASS_STATUS as OWNER_OVERRIDE_PASS,
    verify as verify_owner_override,
)
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1 import (
    PASS_STATUS as CDX_RELEASE_PASS,
    verify as verify_cdx_release,
)
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2 import (
    PASS_STATUS as AMENDMENT_PASS,
    verify as verify_amendment,
)
from scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1 import (
    PASS_STATUS as B4_RELEASE_PASS,
    verify as verify_b4_release,
)
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = ROOT / "configs" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_timing_override_v1.json"
CDX_RELEASE = ROOT / "configs" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_release_v1.json"
AMENDMENT = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_execution_amendment_v2.json"
B4_RELEASE = ROOT / "configs" / "target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1.json"
STATE_REGISTRY = ROOT / "registry" / "analyses" / "current_test_suite_lifecycle_v1.json"


class CurrentArtifactLifecycleV1Tests(unittest.TestCase):
    def _assert_registered_outputs(self, roles: set[str]) -> None:
        state = json.loads(STATE_REGISTRY.read_text(encoding="utf-8"))
        outputs = {item["role"]: item for item in state["consumed_outputs"]}
        self.assertTrue(roles <= set(outputs))
        for role in roles:
            item = outputs[role]
            path = Path(item["path"])
            self.assertTrue(path.is_file(), role)
            self.assertEqual(sha256_file(path), item["sha256"], role)

    def test_owner_override_verifies_after_consumption(self) -> None:
        result = verify_owner_override(OVERRIDE, require_output_absent=False)
        self.assertEqual(result["status"], OWNER_OVERRIDE_PASS, result["errors"])
        self._assert_registered_outputs({"a1_execution_report", "a1_result_qa_v2"})

    def test_owner_override_synthetic_execution_uses_explicit_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            override_qa = directory / "override_qa.json"
            qa = verify_owner_override(OVERRIDE, require_output_absent=False)
            override_qa.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output = directory / "report.json"

            def fetcher(url, contract, counter):
                counter[0] += 1
                fields = contract["query"]["fields"]
                payload = json.dumps([
                    fields,
                    ["20260209193325", "https://lionpoint.com/", "200", "text/html", "A" * 32],
                ]).encode("utf-8")
                return payload, {"http_status": 200, "content_type": "application/json", "response_bytes": len(payload)}

            report = execute(
                OVERRIDE,
                override_qa,
                datetime.fromisoformat("2026-10-23T21:31:00+07:00"),
                fetcher=fetcher,
                output_override=output,
            )
            result = verify_override_result(OVERRIDE, override_qa, output, require_frozen_output_path=False)
        self.assertEqual(report["network_request_count"], 1)
        self.assertEqual(report["safety_contract"]["archived_page_download_operations"], 0)
        self.assertEqual(result["status"], "PASS_OWNER_OVERRIDE_ALTERNATE_CANDIDATE_SELECTED_SEPARATE_CAPTURE_RELEASE_MAY_BE_PREPARED")
        self.assertFalse(result["decision"]["capture_authorized_by_this_qa"])

    def test_alternate_cdx_release_verifies_after_consumption(self) -> None:
        result = verify_cdx_release(CDX_RELEASE, require_output_absent=False)
        self.assertEqual(result["status"], CDX_RELEASE_PASS, result["errors"])
        self._assert_registered_outputs({"a1_execution_report", "a1_result_qa_v2"})

    def test_b5_amendment_verifies_after_consumption(self) -> None:
        result = verify_amendment(AMENDMENT, require_output_absent=False)
        self.assertEqual(result["status"], AMENDMENT_PASS, result["errors"])
        self.assertFalse(result["checks"]["output_absent"])
        self._assert_registered_outputs({"b5_execution_report", "b5_result_qa"})

    def test_b4_release_verifies_after_consumption(self) -> None:
        result = verify_b4_release(B4_RELEASE, require_output_absent=False)
        self.assertEqual(result["status"], B4_RELEASE_PASS, result["errors"])
        self.assertFalse(result["checks"]["network_execution_allowed_now"])
        self._assert_registered_outputs({"b5_execution_report", "b5_result_qa"})


if __name__ == "__main__":
    unittest.main()
